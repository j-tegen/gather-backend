from django.contrib.auth import get_user_model

import graphene
from graphene_django import DjangoObjectType
from events.models import Profile, Location
from events.enums import Gender
from events.utilities import permission_self_or_superuser


class UserType(DjangoObjectType):
    class Meta:
        model = get_user_model()


class ProfileType(DjangoObjectType):
    gender = Gender()
    class Meta:
        model = Profile
        exclude_fields = ['gender']

    def resolve_gender(self, info, **kwargs):
        return permission_self_or_superuser(
            parent_user=self.user_id,
            field=self.gender,
            user=info.context.user
        )

    def resolve_birth_date(self, info, **kwargs):
        return permission_self_or_superuser(
            parent_user=self.user_id,
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
        user = get_user_model()(
            username=username,
            email=email,
        )
        user.set_password(password)
        user.save()

        location = Location(
            city=location_data.city,
            country=location_data.country,
            street=location_data.street,
            longitude=location_data.longitude,
            latitude=location_data.latitude,
        )
        location.save()

        profile = Profile(
            user=user,
            location=location,
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            description=profile_data.description,
            birth_date=profile_data.birth_date,
            gender=profile_data.gender,
            email=email
        )
        profile.save()

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


class Mutation(graphene.ObjectType):
    register = Register.Field()
    updateProfile = UpdateProfile.Field()


class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    user = graphene.Field(UserType, id=graphene.Int())
    users = graphene.List(UserType)

    profile = graphene.Field(ProfileType, id=graphene.Int())

    def resolve_user(self, info, id):
        return get_user_model().objects.get(pk=id)

    def resolve_users(self, info):
        return get_user_model().objects.all()

    def resolve_profile(self, info, id):
        return Profile.objects.filter(pk=id)

    def resolve_me(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')

        return user