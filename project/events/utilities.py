from .models import Tag, Location
import requests
import string
import random
from project.settings import GOOGLE_MAPS_API_KEY

def queryset_skip_next(qs, first=None, skip=None):
    if skip:
        qs = qs[skip::]
    if first:
        qs = qs[:first]

    return qs


def permission_self_or_superuser(parent_user, field, user, rejection_value=None):
    if user.is_superuser:
        return field
    if user.id == parent_user:
        return field
    return rejection_value


def set_tags(parent, tags):
    existing_ids = [tag.id for tag in parent.tags.all()]
    all_tags = []
    for t in tags:
        if t.id:
            tag = Tag.objects.get(pk=t.id)
            all_tags.append(tag)
            print(all_tags)
            continue
        tag = Tag.objects.filter(text__iexact=t.text).first()
        if not tag:
            tag = Tag(
                text=t.text
            )
            tag.save()
        all_tags.append(tag)

    request_ids = [tag.id for tag in all_tags]
    delete_ids = list(set(existing_ids) - set(request_ids))

    for tag in all_tags:
        parent.tags.add(tag)

    for tag_id in delete_ids:
        tag = Tag.objects.get(pk=tag_id)
        parent.tags.remove(tag)


def add_or_update_location(location_data):
    location = Location()

    (lat, lng, g_id, formatted_address) = get_google_geo_info(
        country=location_data.country,
        city=location_data.city,
        street=location_data.street
    )

    if not g_id:
        return None

    location = Location.objects.filter(
        google_id=g_id).first()

    if not location:
        location = Location()

    location.city=location_data.city
    location.country=location_data.country
    location.street=location_data.street

    location.latitude=lat
    location.longitude=lng
    location.google_id = g_id
    location.google_formatted_address = formatted_address
    location.save()
    return location

def get_google_geo_info(country, city, street):
    address = "{}, {}, {}".format(street, city, country)
    response = requests.get(
        'https://maps.googleapis.com/maps/api/geocode/json?address={0}&key={1}'.format(
            address, GOOGLE_MAPS_API_KEY)).json()['results']

    if len(response) == 0:
        return (None, None, None, None)


    response = response[0]
    location = response['geometry']['location']

    return (location['lat'], location['lng'], response['place_id'], response['formatted_address'])



def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))