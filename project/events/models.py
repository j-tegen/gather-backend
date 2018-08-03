from django.db import models
from django.conf import settings
from django.db.models import Value, Func, F
import math

from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created)
def extend_sqlite(connection=None, **kwargs):
    if connection.vendor == "sqlite":
        # sqlite doesn't natively support math functions, so add them
        cf = connection.connection.create_function
        cf('SQRT', 1, math.sqrt)
        cf('ATAN2', 2, math.atan2)
        cf('POW', 2, math.pow)
        cf('ACOS', 1, math.acos)
        cf('COS', 1, math.cos)
        cf('RADIANS', 1, math.radians)
        cf('SIN', 1, math.sin)


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
    profile_picture = models.TextField(blank=True)


    @property
    def full_name(self):
        return "{} {}".format(self.first_name, self.last_name)


class LocationManager(models.Manager):
    def nearby(self, latitude, longitude, proximity):
        """
        Return all object which distance to specified coordinates
        is less than proximity given in kilometers
        """
        # Great circle distance formula

        earth_radius=Value(6371.0, output_field=models.FloatField())

        f1=Func(F('latitude'), function='RADIANS', output_field=models.FloatField())
        latitude2=Value(latitude, output_field=models.FloatField())
        f2=Func(latitude2, function='RADIANS', output_field=models.FloatField())

        l1=Func(F('longitude'), function='RADIANS', output_field=models.FloatField())
        longitude2=Value(longitude, output_field=models.FloatField())
        l2=Func(longitude2, function='RADIANS', output_field=models.FloatField())

        d_lat=Func(F('latitude'), function='RADIANS', output_field=models.FloatField()) - f2
        d_lng=Func(F('longitude'), function='RADIANS', output_field=models.FloatField()) - l2

        sin_lat = Func(d_lat/2, function='SIN', output_field=models.FloatField())
        cos_lat1 = Func(f1, function='COS', output_field=models.FloatField())
        cos_lat2 = Func(f2, function='COS', output_field=models.FloatField())
        sin_lng = Func(d_lng/2, function='SIN', output_field=models.FloatField())

        a = Func(sin_lat, 2, function='POW', output_field=models.FloatField()) + cos_lat1 * cos_lat2 * Func(sin_lng, 2, function='POW', output_field=models.FloatField())
        c = 2 * Func(Func(a, function='SQRT', output_field=models.FloatField()), Func(1 - a, function='SQRT', output_field=models.FloatField()), function='ATAN2', output_field=models.FloatField())
        d = earth_radius * c

        res = self.get_queryset()\
                    .exclude(latitude=None)\
                    .exclude(longitude=None)\
                    .annotate(d=d)\
                    .filter(d__lte=proximity)\
                    .order_by('distance')
        return res



class Location(BaseModel):
    objects = LocationManager()

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

