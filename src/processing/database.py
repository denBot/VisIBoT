import mongoengine as mongo
from mongoengine.errors import NotUniqueError
from datetime import datetime


class GeoData(mongo.Document):
    """
    Server/IP Address information pulled from payload data of
    BadPackets results
    """
    ip_address        = mongo.StringField(required=True, primary_key=True)
    occurrences       = mongo.IntField(default=0)
    updated_at        = mongo.DateTimeField(default=datetime.utcnow)
    data              = mongo.DictField(required=True)
    hostname          = mongo.StringField(required=False)
    tags              = mongo.DictField(required=False)
    server_type       = mongo.StringField(
        required=True,
        choices=[
            "C2 Server",
            "Loader Server",
            "Report Server",
            "Bot",
            "Unknown"
        ]
    )


class Payload(mongo.Document):
    """
    Malware payload information retrieved from BadPackets results
    """
    url               = mongo.StringField(required=True, primary_key=True)
    occurrences       = mongo.IntField(default=0)
    lisa              = mongo.DictField(required=False)
    ip_address        = mongo.ReferenceField(GeoData, required=True)
    updated_at        = mongo.DateTimeField(default=datetime.utcnow)
    candidate_C2s     = mongo.ListField(mongo.ReferenceField(GeoData, required=False), required=False, default=[])


class Result(mongo.Document):
    """
    BadPackets Result JSON information
    """
    event_id          = mongo.StringField(required=True, primary_key=True)
    source_ip_address = mongo.ReferenceField(GeoData, required=True)
    country           = mongo.StringField(required=True, max_length=4)
    user_agent        = mongo.DictField(required=True)
    payload           = mongo.StringField(required=True)
    post_data         = mongo.StringField(required=True)
    target_port       = mongo.IntField(required=True)
    protocol          = mongo.StringField(required=True)
    event_count       = mongo.IntField(required=True)
    first_seen        = mongo.StringField(required=True)
    last_seen         = mongo.StringField(required=True)
    tags              = mongo.ListField(mongo.DictField(required=True), required=True)
    scanned_urls      = mongo.ListField(mongo.ReferenceField(Payload, required=False), required=False)
    affiliated_ips    = mongo.ListField(mongo.ReferenceField(GeoData, required=False), required=False)
    updated_at        = mongo.DateTimeField(default=datetime.utcnow)


def payload_create_or_update(url, ip, now):
    try:
        payload = Payload(
            url=url,
            ip_address=ip,
            updated_at=now
        )
        payload.save()
    except NotUniqueError:
        payload = Payload.objects(url=url).first()
        payload.updated_at = now
        payload.occurrences += 1
        payload.save()

    return payload


def result_create_or_update(event_id, result_data, now):
    try:
        result = Result(**result_data)
        result.save()
    except (NotUniqueError, mongo.DuplicateKeyError):
        result = Result.objects(event_id=event_id).first()
        result.scanned_payloads = list(set(result.scanned_payloads + result_data['scanned_payloads']))
        result.updated_at = now
        result.save()

    return result


def geodata_create_or_update(ip, hostname, server_type, geodata, now, tags=None):
    if tags:
        cves = []
        categories = []
        descriptions = []

        for tag in tags:
            cves.append(tag['cve'])
            categories.append(tag['category'])
            descriptions.append(tag['description'])

        tags = {
            'cves': cves,
            'categories': categories,
            'descriptions': descriptions,
        }

    try:
        geodata = GeoData(
            ip_address=ip,
            hostname=hostname,
            server_type=server_type,
            data=geodata,
            tags=tags,
        )
        geodata.save()
    except NotUniqueError:
        geodata = GeoData.objects(ip_address=ip).first()
        geodata.updated_at = now
        geodata.occurrences += 1
        geodata.save()

    return geodata
