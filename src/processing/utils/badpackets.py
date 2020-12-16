# pylama:ignore=E402:ignore=E702
import sys; sys.path.append("..")
import database as db
import time
from datetime import datetime, timedelta
from requests.exceptions import HTTPError
from contextlib import suppress
from utils.misc import url_parser, validate_url, useragent_parser, get_ip_hostname
from utils.geodata import geoip_info


FIRST_RUN_HOURS = 24
BASE_PARAMS = {
    'limit': 1000,
}
PROC_PARAMS = [
    [('payload', 'chmod')],
    [('post_data', 'chmod')],
    [('tags', 'Mirai')],
    [('tags', 'IoT')],
    [('tags', 'Bashlite')],
    [('tags', 'Botnet')],
]


def has_botnet_tag(tags):
    for tag in tags:
        desc = tag['description'].lower()
        category = tag['category'].lower()
        if "scan" in desc or "botnet" in category:
            return True


def query_badpackets(api, first_run=False):
    """
    Queries the BadPackets API for N param combinations in PROC_PARAMS
    If the initial query result contains more than 1 page, all remaining
    pages are also queried and collected.

    Args:
        api (BadPacketsAPI): The BadPackets wrapper API instance to be used.
        first_run (bool, optional): Defaults to False. Determines if FIRST_RUN_HOURS
            should be used to calculated after_dt instead of the default (1 hour).

    Returns:
        list: A list of BadPackets Results (dictionaries)
    """
    all_results = []

    after_dt = (
        datetime.utcnow() - timedelta(hours=FIRST_RUN_HOURS if first_run else 2)
    ).strftime('%Y-%m-%dT%H:%M:%SZ')

    print(f"Querying BadPackets (last seen after {after_dt})")

    for param_list in PROC_PARAMS:
        params = BASE_PARAMS.copy()
        params['last_seen_after'] = after_dt

        param_str = "&".join([f"{p}={v}" for p, v in param_list])

        for param, value in param_list:
            params[param] = value

        print(f" -> Querying params: {param_str}")

        with suppress(HTTPError, AttributeError):
            time.sleep(2)
            results_json = api.query(params).json()
            all_results += results_json['results']
            page_num = 2

            while results_json['next']:
                print("    ... Querying Page", page_num)
                time.sleep(2)
                results_json = api.get_url(results_json['next']).json()
                all_results += results_json['results']
                page_num += 1

    return all_results


def store_result(event_id, result_data):
    """
    Takes a given event_id and results dict for a BadPackets result
    and processes it:
    - ignore if result is already stored or no geodata can be found
    - extract URls in payload data and process each URL
        - validate and obtain IP and hostname for each URL
        - add new Payload & GeoData entry for each URL / IP
    - insert new Result and GeoData entry for the given result

    Args:
        event_id (str): The event_id of the given BadPackets Result
        result_data (dict): The dictionary (JSON Object) result data
    """
    scanned_payloads = []
    now = datetime.utcnow()

    existing_result = db.Result.objects(event_id=event_id).first()

    if existing_result:
        existing_result.updated_at = now
        existing_result.save()
        return []

    payload_data = result_data['post_data'] + result_data['payload']
    validated_urls = [validate_url(url) for url in url_parser(payload_data)]
    validated_urls = [url for url in validated_urls if url]

    for url_info in validated_urls:
        url, hostname, ip = url_info
        existing_payload = db.Payload.objects(url=url).first()

        if existing_payload:
            existing_payload.updated_at = now
            existing_payload.save()
            scanned_payloads.append(existing_payload)
            continue

        geodata = geoip_info(ip)

        if not geodata:
            continue

        db.geodata_create_or_update(ip, hostname, "Loader Server", geodata, now)
        payload = db.payload_create_or_update(url, ip, now)
        scanned_payloads.append(payload)

    geodata = geoip_info(result_data['source_ip_address'])

    if geodata:
        ip = result_data['source_ip_address']
        hostname = get_ip_hostname(ip)

        if has_botnet_tag(result_data['tags']):
            server_type = "Bot"
        elif scanned_payloads and "<?xml" not in result_data['post_data']:
            server_type = "Report Server"
        else:
            server_type = "Unknown"

        geodata = db.geodata_create_or_update(ip, hostname, server_type, geodata, now)

        result_data['source_ip_address'] = geodata.id
        result_data['user_agent'] = useragent_parser(result_data['user_agent'])
        result_data['scanned_payloads'] = scanned_payloads

        db.result_create_or_update(event_id, result_data, now)

    return scanned_payloads
