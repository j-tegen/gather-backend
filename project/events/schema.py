import graphene
from graphene_django import DjangoObjectType
from graphql import GraphQLError

from .models import Event, Location, Participant, Profile, Tag, Post
from users.schema import UserType
from django.db.models import Q, Count
from .utilities import queryset_skip_next, set_tags, update_location, get_lat_long
from .enums import ParticipantStatus



class ParticipantType(DjangoObjectType):
    status = ParticipantStatus()
    class Meta:
        model = Participant
        exclude_fields = ['status']

    def resolve_status(self, info, **kwargs):
        return self.status


class LocationType(DjangoObjectType):
    class Meta:
        model = Location


class EventType(DjangoObjectType):
    class Meta:
        model = Event


class TagType(DjangoObjectType):
    class Meta:
        model = Tag


class PostType(DjangoObjectType):
    class Meta:
        model = Post


class EventInput(graphene.InputObjectType):
    id = graphene.ID()
    title = graphene.String(required=True)
    description = graphene.String()
    start_date = graphene.types.datetime.Date(required=True)
    start_time = graphene.types.datetime.Time(required=True)
    end_date = graphene.types.datetime.Date()
    end_time = graphene.types.datetime.Time()
    max_participants = graphene.Int()
    min_participants = graphene.Int()
    event_type = graphene.String(required=True)


class LocationInput(graphene.InputObjectType):
    id = graphene.Int()
    city = graphene.String(required=True)
    country = graphene.String(required=True)
    street = graphene.String()


class TagInput(graphene.InputObjectType):
    id = graphene.Int()
    text = graphene.String(required=True)


class CreatePost(graphene.Mutation):
    post = graphene.Field(PostType)

    class Arguments:
        id_event = graphene.Int(required=True)
        title = graphene.String()
        body = graphene.String(required=True)

    def mutate(self, info, id_event, title, body):
        user = info.context.user or None
        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        event = Event.objects.get(pk=id_event)

        post = Post(
            user=user,
            event=event,
            title=title,
            body=body
        )
        post.save()
        return CreatePost(post=post)


class CreateParticipant(graphene.Mutation):
    participant = graphene.Field(ParticipantType)

    class Arguments:
        id_event = graphene.Int(required=True)
        status = ParticipantStatus(required=True)

    def mutate(self, info, id_event, status):
        user = info.context.user or None
        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        event = Event.objects.get(pk=id_event)

        participant = Participant(
            user=user,
            event=event,
            status=status,
        )
        participant.save()
        return CreateParticipant(participant=participant)


class UpdateParticipant(graphene.Mutation):
    participant = graphene.Field(ParticipantType)
    class Arguments:
        id = graphene.Int(required=True)
        status = ParticipantStatus(required=True)

    def mutate(self, info, id, status):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        participant = Participant.objects.get(pk=id)

        if user.id != participant.user.id:
            raise GraphQLError('You can only update your own participations')

        participant.status=status
        participant.save()
        return UpdateParticipant(participant=participant)


class UpdateLocation(graphene.Mutation):
    location = graphene.Field(LocationType)

    class Arguments:
        location_data = LocationInput(required=True)

    def mutate(self, info, location_data):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        location = update_location(location_data)
        return UpdateLocation(location=location)


class CreateEvent(graphene.Mutation):
    event = graphene.Field(EventType)

    class Arguments:
        event_data = EventInput(required=True)
        location_data = LocationInput(required=True)
        tags = graphene.List(TagInput)

    def mutate(self, info, event_data, location_data):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        location = Location()
        if location_data.id:
            location = update_location(location_data)
        else:
            (lat, lng) = get_lat_long(
                country=location_data.country,
                city=location_data.city,
                street=location_data.street
            )
            location = Location(
                city=location_data.city,
                country=location_data.country,
                street=location_data.street,
                latitude=lat,
                longitude=lng,
            )
            location.save()

        event = Event(
            title=event_data.title,
            description=event_data.description,
            start_date=event_data.start_date,
            start_time=event_data.start_time,
            end_date=event_data.end_date,
            end_time=event_data.end_time,
            location=location,
            organizer=user,
            min_participants=event_data.min_participants,
            max_participants=event_data.max_participants,
        )
        event.save()
        return CreateEvent(event=event)


class UpdateEvent(graphene.Mutation):
    event = graphene.Field(EventType)

    class Arguments:
        event_data = EventInput(required=True)
        tags = graphene.List(TagInput, required=False)

    def mutate(self, info, event_data, tags = []):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        event = Event.objects.get(pk=event_data.id, organizer=user.id)

        set_tags(event, tags)

        event.title=event_data.title
        event.description=event_data.description
        event.start_date=event_data.start_date
        event.start_time=event_data.start_time
        event.end_date=event_data.end_date
        event.end_time=event_data.end_time
        event.organizer=user
        event.save()
        return UpdateEvent(event=event)


class DeleteEvent(graphene.Mutation):
    id = graphene.Int()

    class Arguments:
        id = graphene.Int(required=True)

    def mutate(self, info, id):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')
        event = Event.objects.get(pk=id)

        if user.id != event.organizer.id:
            raise GraphQLError('You can only delete your own events!')

        event.delete()
        return DeleteEvent(id=id)



class CreateTag(graphene.Mutation):
    tag = graphene.Field(TagType)

    class Arguments:
        text = graphene.String()

    def mutate(self, info, text):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        tag = Tag.objects.filter(text__iexact=text).first()
        if tag:
            return CreateTag(tag=tag)

        tag = Tag(
            text=text
        )
        tag.save()
        return CreateTag(tag=tag)


class Mutation(graphene.ObjectType):
    create_event = CreateEvent.Field()
    update_event = UpdateEvent.Field()
    delete_event = DeleteEvent.Field()
    create_participant = CreateParticipant.Field()
    update_participant = UpdateParticipant.Field()
    create_tag = CreateTag.Field()
    create_post = CreatePost.Field()
    update_location = UpdateLocation.Field()


class Query(graphene.ObjectType):
    events = graphene.List(
        EventType,
        search=graphene.String(),
        first=graphene.Int(),
        skip=graphene.Int(),
    )

    close_events = graphene.List(
        EventType,
        city=graphene.String(),
        country=graphene.String(),
        first=graphene.Int(),
        skip=graphene.Int(),
    )

    event_participants = graphene.List(
        ParticipantType,
        id_event=graphene.Int()
    )

    event_posts = graphene.List(
        PostType,
        id_event=graphene.Int()
    )

    tags = graphene.List(
        TagType,
        search=graphene.String(),
        first=graphene.Int(),
        skip=graphene.Int(),
    )

    my_organized_events = graphene.List(EventType)

    event = graphene.Field(EventType, id=graphene.Int())

    def resolve_tags(self, info, search=None, first=None, skip=None, **kwargs):
        qs = Tag.objects.all()
        if search:
            filter = (
                Q(text__icontains=search)
            )
            qs = qs.filter(filter)
        qs = qs.annotate(num_events=Count('events')).order_by('-num_events')
        return queryset_skip_next(qs=qs, first=first, skip=skip)

    def resolve_event_participants(self, info, id_event, **kwargs):
        return Participant.objects.filter(event=id_event)

    def resolve_event_posts(self, info , id_event, **kwargs):
        return Post.objects.filter(event=id_event)

    def resolve_event(self, info, id, **kwargs):
        return Event.objects.get(pk=id)

    def resolve_my_organized_events(self, info):
        user = info.context.user or None

        if user.is_anonymous:
            raise GraphQLError('User not logged in!')

        return Event.objects.filter(organizer=user)

    def resolve_events(self, info, search=None, first=None, skip=None, **kwargs):
        qs = Event.objects.all()

        if search:
            filter = (
                Q(title__icontains=search)
            )
            qs = qs.filter(filter)

        return queryset_skip_next(qs=qs, first=first, skip=skip)

    def resolve_close_events(
            self,
            info,
            city,
            country,
            first=None,
            skip=None,
            **kwargs):

        qs = Event.objects.all()

        filter = (
            Q(location__city__iexact=city) &
            Q(location__country__iexact=country)
        )
        qs = qs.filter(filter)

        return queryset_skip_next(qs=qs, first=first, skip=skip)
