from django.contrib.auth import get_user_model
from django.db import transaction

import graphene
from graphql import GraphQLError
from graphene_django import DjangoObjectType
from events.models import Profile, Location, Friendship
from events.enums import Gender, FriendStatus
from events.utilities import permission_self_or_superuser, add_or_update_location


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
        exclude_fields = ['gender']

    def resolve_gender(self, info, **kwargs):
        return permission_self_or_superuser(
            parent_user=self.profile_id,
            field=self.gender,
            user=info.context.user
        )

    def resolve_birth_date(self, info, **kwargs):
        return permission_self_or_superuser(
            parent_user=self.profile_id,
            field=self.birth_date,
            user=info.context.user
        )


class ProfileInput(graphene.InputObjectType):
    id = graphene.ID()
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    description = graphene.String()
    email = graphene.String()
    birth_date = graphene.types.datetime.Date()
    gender = Gender(required=True)


class ProfileLocationInput(graphene.InputObjectType):
    id = graphene.Int()
    city = graphene.String(required=True)
    country = graphene.String(required=True)
    street = graphene.String()
    longitude = graphene.Float()
    latitude = graphene.Float()


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
        location_data = ProfileLocationInput()

    def mutate(self, info, profile_data, location_data=None):
        user = info.context.user or None
        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        if location_data:
            location = Location.objects.get(pk=location_data.id)
            location.city=location_data.city
            location.country=location_data.country
            location.street=location_data.street
            location.longitude=location_data.longitude
            location.latitude=location_data.latitude
            location.save()

        profile = user.profile
        profile.first_name=profile_data.first_name
        profile.last_name=profile_data.last_name
        profile.description=profile_data.description
        profile.birth_date=profile_data.birth_date
        profile.gender=profile_data.gender
        profile.save()

        return UpdateProfile(profile=profile)


class AddFriend(graphene.Mutation):
    friend = graphene.Field(FriendshipType)

    class Arguments:
        profile_id = graphene.Int(required=True)

    def mutate(self, info, profile_id):
        user = info.context.user or None
        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        friend = Friendship(status="PENDING")
        friend.requested_by = user.id
        friend.profiles.add(use.profile.id, profile_id)

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
    removeFriend = RemoveFriend.Field()


class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    user = graphene.Field(UserType, id=graphene.Int())
    users = graphene.List(UserType)

    profile = graphene.Field(ProfileType, id=graphene.Int())
    profiles = graphene.List(ProfileType)

    my_friends = graphene.List(ProfileType)

    friendships = graphene.List(FriendshipType)

    def resolve_user(self, info, id):
        return get_user_model().objects.get(pk=id)

    def resolve_users(self, info):
        return get_user_model().objects.all()

    def resolve_profile(self, info, id):
        return Profile.objects.filter(pk=id)

    def resolve_profiles(self, info):
        return Profile.objects.all()

    def resolve_me(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')

        return user

    def resolve_my_friends(self, info, name_filter=None, **kwargs):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        qs = Profile.objects.filter(friends__profile__id__exact=user.profile.id)
        if name_filter:
            filter = (
                Q(name__icontains=name_filter)
            )
            qs = qs.filter(filter)

        return qs

    def resolve_friendships(self, info, **kwargs):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        return Friendship.objects.all()
