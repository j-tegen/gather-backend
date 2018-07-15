from django.db import models
from django.conf import settings

class BaseModel(models.Model):
    created_time = models.DateTimeField(auto_now_add=True)
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Event(BaseModel):
    title = models.CharField(max_length=100, blank=False)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    start_time = models.TimeField()
    end_date = models.DateField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="events_organized",
        on_delete=models.CASCADE)
    location = models.ForeignKey(
        'events.Location',
        related_name='events',
        on_delete=models.CASCADE)
    min_participants = models.PositiveIntegerField()
    max_participants = models.PositiveIntegerField()
    event_type = models.CharField(max_length=100)


class Participant(BaseModel):
    class Meta:
        unique_together = (("user", "event"),)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="events_participated",
        on_delete=models.CASCADE)
    event = models.ForeignKey(
        'events.Event',
        related_name='participants',
        on_delete=models.CASCADE)
    status = models.CharField(
        max_length=30,
        choices=(
            ("INTERESTED", "Interested"),
            ("GOING", "Going"),
            ("NOTGOING", "Not going"),
            ("INVITED", "Invited")),
            default="INTERESTED")


class Friendship(BaseModel):
    status = models.CharField(
        max_length=20,
        choices=(
            ("PENDING", "Pedning"),
            ("FRIENDS", "Friends"),
        ), default="FRIENDS"
    )
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True)
    profiles = models.ManyToManyField('Profile', blank=True)


class Profile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)
    location = models.ForeignKey(
        'events.Location',
        related_name='profiles',
        on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50, blank=False)
    last_name = models.CharField(max_length=50, blank=False)
    description = models.TextField(blank=True)
    email = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=20,
        choices=(
            ("MALE", "Male"),
            ("FEMALE", "Female"),
            ("OTHER", "Other"),
            ("NOANSWER", "")
        ),
        default="NOANSWER")
    friends = models.ManyToManyField('Friendship', through=Friendship.profiles.through, blank=True)

    @property
    def full_name(self):
        return "{} {}".format(self.first_name, self.last_name)


class Location(BaseModel):
    city = models.CharField(max_length=100, blank=False)
    country = models.CharField(max_length=100, blank=False)
    street = models.CharField(max_length=100, blank=True)
    google_id = models.CharField(max_length=50, blank=True)
    google_formatted_address = models.CharField(max_length=1000, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)


class Tag(BaseModel):
    text = models.CharField(max_length=20, blank=False)
    events = models.ManyToManyField('events.Event', related_name='tags')


class Post(BaseModel):
    title = models.CharField(max_length=50)
    body = models.TextField(max_length=1000, blank=False)
    event = models.ForeignKey('events.Event', related_name='posts', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)
