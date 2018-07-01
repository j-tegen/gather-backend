from .models import Tag, Location
import requests
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


def update_location(location_data):
    location = Location.objects.get(pk=location_data.id)
    location.city=location_data.city
    location.country=location_data.country
    location.street=location_data.street

    (lat, lng) = get_lat_long(
        country=location_data.country,
        city=location_data.city,
        street=location_data.street
    )
    location.latitude=lat
    location.longitude=lng
    location.save()
    return location

def get_lat_long(country, city, street):
    address = "{}, {}, {}".format(street, city, country)
    response = requests.get(
        'https://maps.googleapis.com/maps/api/geocode/json?address={0}&key={1}'.format(address, GOOGLE_MAPS_API_KEY))
    location = response.json()['results'][0]['geometry']['location']

    return (location['lat'], location['lng'])

