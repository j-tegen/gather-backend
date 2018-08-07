from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Count
from functools import reduce
import boto3
import io
import graphene

from PIL import Image
from graphql import GraphQLError
from graphene_file_upload import Upload
from graphene_django import DjangoObjectType
from events.models import Profile, Location, Friendship
from events.enums import Gender, FriendStatus
from events.utilities import permission_self_or_superuser, add_or_update_location, id_generator, queryset_skip_next
from project.settings import S3_ACCESS_KEY, S3_SECRET_ACCESS_KEY, S3_PROFILE_PICTURE_BUCKET


session = boto3.Session(
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_ACCESS_KEY
)

s3 = session.resource('s3')

class UserType(DjangoObjectType):
    class Meta:
        model = get_user_model()

class FriendshipType(DjangoObjectType):
    class Meta:
        model = Friendship
    status = FriendStatus()

class ProfileType(DjangoObjectType):
    gender = Gender()
    class Meta:
        model = Profile


class ProfileInput(graphene.InputObjectType):
    id = graphene.ID()
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    description = graphene.String()
    email = graphene.String()
    birth_date = graphene.types.datetime.Date()
    gender = Gender(required=True)


class ProfileLocationInput(graphene.InputObjectType):
    google_id = graphene.String(required=False)
    city = graphene.String(required=True)
    country = graphene.String(required=True)
    street = graphene.String()


class CropInput(graphene.InputObjectType):
    x0 = graphene.Int()
    x1 = graphene.Int()
    y0 = graphene.Int()
    y1 = graphene.Int()


class Register(graphene.Mutation):
    user = graphene.Field(UserType)

    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)
        email = graphene.String(required=True)
        profile_data = ProfileInput(required=True)
        location_data = ProfileLocationInput(required=True)

    def mutate(self, info, username, password, email, profile_data, location_data):
        user = get_user_model().objects.filter(email=email)

        if user:
            raise GraphQLError('There is already a user with that email')
        try:
            with transaction.atomic():
                user = get_user_model()(
                    username=username,
                    email=email,
                )
                user.set_password(password)
                user.save()

                location = add_or_update_location(location_data)

                profile = Profile(
                    user=user,
                    location=location,
                    first_name=profile_data.first_name,
                    last_name=profile_data.last_name,
                    description='',
                    birth_date=profile_data.birth_date,
                    gender=profile_data.gender,
                    email=email
                )
                profile.save()
        except Exception as e:
            raise GraphQLError(e)

        return Register(user=user)


class UpdateProfile(graphene.Mutation):
    profile = graphene.Field(ProfileType)

    class Arguments:
        profile_data = ProfileInput(required=True)

    def mutate(self, info, profile_data):
        user = info.context.user or None
        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        profile = user.profile
        profile.first_name=profile_data.first_name
        profile.last_name=profile_data.last_name
        profile.description=profile_data.description
        profile.birth_date=profile_data.birth_date
        profile.gender=profile_data.gender
        profile.email=profile_data.email
        profile.save()

        return UpdateProfile(profile=profile)


class ProfilePicture(graphene.Mutation):
    class Arguments:
        profile_id = graphene.Int(required=True)
        file = Upload(required=True)
        crop = CropInput(required=True)


    profile = graphene.Field(ProfileType)

    def mutate(self, info, profile_id, file, crop, **kwargs):
        profile = Profile.objects.get(pk=profile_id)

        uploaded_file = info.context.FILES.get(file)

        box = (crop.x0, crop.y0, crop.x1, crop.y1)
        image = Image.open(uploaded_file)
        cropped_image = image.crop(box)

        extension = uploaded_file.name.split('.')[1]
        filename = "profile_picture_{}__{}.{}".format(
            profile_id,
            id_generator(),
            extension
        )

        in_mem_file = io.BytesIO()
        cropped_image.save(in_mem_file, format=extension)
        in_mem_file.seek(0)

        s3.Bucket(S3_PROFILE_PICTURE_BUCKET).put_object(
            Key=filename,
            Body=in_mem_file,
            ACL='public-read')

        old_url = profile.profile_picture
        if old_url:
            old_filename = old_url[::-1].split('/')[0][::-1]
            s3.Object(S3_PROFILE_PICTURE_BUCKET, old_filename).delete()

        profile.profile_picture = "https://s3-eu-west-1.amazonaws.com/{}/{}".format(
            S3_PROFILE_PICTURE_BUCKET,
            filename,
        )

        profile.save()
        return ProfilePicture(profile=profile)


class HandleFriendRequest(graphene.Mutation):
    friendship = graphene.Field(FriendshipType)

    class Arguments:
        friendship_id = graphene.Int(required=True)
        status = FriendStatus(required=True)

    def mutate(self, info, friendship_id, status):
        user = info.context.user or None
        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        friendship = Friendship.objects.get(pk=friendship_id)
        friendship.status = status
        friendship.save()

        return HandleFriendRequest(friendship=friendship)


class AddFriend(graphene.Mutation):
    friend = graphene.Field(FriendshipType)

    class Arguments:
        profile_id = graphene.Int(required=True)

    def mutate(self, info, profile_id):
        user = info.context.user or None
        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        friendships = reduce(
            lambda qs,
            pk: qs.filter(profiles=pk),
            [profile_id, user.profile.id],
            Friendship.objects.all()
        )

        if friendships:
            raise GraphQLError('Relationship already exists!')

        friend = Friendship(status="PENDING")
        friend.requested_by = user
        friend.save()
        friend.profiles.add(user.profile.id, profile_id)


        return AddFriend(friend=friend)


class RemoveFriend(graphene.Mutation):
    profile = graphene.Field(FriendshipType)

    class Arguments:
        friendship_id = graphene.Int(required=True)

    def mutate(self, info, friendship_id):
        user = info.context.user or None
        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        profile = Profile.object.get(pk=friendship.profile.id)
        friendship = Friendship.objects.get(pk=friendship_id)

        friendship.remove()

        return RemoveFriend(profile=profile)


class Mutation(graphene.ObjectType):
    register = Register.Field()
    updateProfile = UpdateProfile.Field()
    addFriend = AddFriend.Field()
    handleFriendRequest = HandleFriendRequest.Field()
    removeFriend = RemoveFriend.Field()
    profile_picture = ProfilePicture.Field()


class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    user = graphene.Field(UserType, id=graphene.Int())
    users = graphene.List(UserType)

    profile = graphene.Field(ProfileType, id=graphene.Int())
    profiles = graphene.List(
        ProfileType,
        search=graphene.String(),
        first=graphene.Int(),
        skip=graphene.Int())

    my_friends = graphene.List(FriendshipType)

    friendships = graphene.List(FriendshipType)

    def resolve_user(self, info, id):
        return get_user_model().objects.get(pk=id)

    def resolve_users(self, info):
        return get_user_model().objects.all()

    def resolve_profile(self, info, id):
        return Profile.objects.filter(pk=id)

    # def resolve_profiles(self, info, search=None):
    #     return Profile.objects.all()

    def resolve_profiles(self, info, search=None, first=None, skip=None, **kwargs):
        qs = Profile.objects.all()


        if search:
            search_words = search.split(' ')
            filters = [(
                Q(first_name__icontains=val) |
                Q(last_name__icontains=val) |
                Q(location__city__icontains=val)
            ) for val in search_words]

            filter = filters.pop()
            for item in filters:
                filter |= item

            qs = qs.filter(filter)
        return queryset_skip_next(qs=qs, first=first, skip=skip)

    def resolve_me(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')

        return user

    def resolve_my_friends(self, info, **kwargs):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        friends = Friendship.objects.filter(profile__id__exact=user.profile.id)

        return friends

    def resolve_friendships(self, info, **kwargs):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        return Friendship.objects.all()
