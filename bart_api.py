from datetime import datetime, timedelta
import logging
import urlparse, urllib, urllib2
from xml.etree.ElementTree import parse
from dateutil import parser, tz
import schedule

from route import Route
from station import Station

API_ROOT = "http://api.bart.gov/api/"
API_KEY = "MW9S-E7SL-26DU-VV8V"
API_TIMEOUT = 5
BART_TIME_CUTOFF = "2:27 AM"

def call_api(script, **kwargs):
    url = urlparse.urljoin(API_ROOT, script)
    kwargs.update({'key': API_KEY})
    args = urllib.urlencode(kwargs)
    logging.info("Making API call: %s?%s" % (url, args))
    response = urllib2.urlopen("%s?%s" % (url, args), timeout=API_TIMEOUT)
    return response

def call_xml_api(script, **kwargs):
    response = call_api(script, **kwargs)
    element_tree = parse(response)
    return element_tree

def call_string_api(script, **kwargs):
    response = call_api(script, **kwargs)
    return response.read()

def extract_xml_timestamp(xml):
    date = xml.find('date').text
    time = xml.find('time').text
    return "%s %s" % (date, time)

def parse_date_time(timestamp):
    no_tz = parser.parse(timestamp, dayfirst=True)
    tz_aware = no_tz.replace(tzinfo=tz.tzlocal())
    return tz_aware

def train_count():
    xml = call_xml_api("bsa.aspx", cmd='count')
    timestamp = extract_xml_timestamp(xml)
    date_time = parse_date_time(timestamp)
    num_trains = int(xml.find('traincount').text)
    return num_trains, date_time

def station_list(system):
    xml = call_xml_api("stn.aspx", cmd='stns')
    xml_stations = xml.find('stations')
    stations = []
    for xml_station in xml_stations:
        name = xml_station.find('name').text
        abbr = xml_station.find('abbr').text
        lat = float(xml_station.find('gtfs_latitude').text)
        lng = float(xml_station.find('gtfs_longitude').text)
        address = xml_station.find('address').text
        city = xml_station.find('city').text
        county = xml_station.find('county').text
        state = xml_station.find('state').text
        zipcode = int(xml_station.find('zipcode').text)
        segments = []

        stations.append(
            Station(abbr, name, lat, lng, segments, system)
        )
    return stations

def route_list(system):
    xml = call_xml_api("route.aspx", cmd='routes')
    xml_routes = xml.find('routes')
    routes = []
    for xml_route in xml_routes:
        number = int(xml_route.find('number').text)

        name, abbr, route_id, origin, dest,\
        direction, color, holidays, stations = route_information(number, system)

        routes.append(
            Route(name, abbr, route_id, origin, dest, direction, number, color, holidays, stations, system)
        )
    return routes

def route_information(route_num, system):
    # TODO: Add support for requesting multiple routes at once
    xml = call_xml_api("route.aspx", cmd='routeinfo', route=route_num)
    xml_routes = xml.find('routes')
    xml_route = xml_routes.find('route')
    name = xml_route.find('name').text
    abbr = xml_route.find('abbr').text
    route_id = xml_route.find('routeID').text
    origin = system.station_for_abbr(xml_route.find('origin').text)
    dest = system.station_for_abbr(xml_route.find('destination').text)
    direction = xml_route.find('direction').text
    color = xml_route.find('color').text
    holidays = bool(xml_route.find('holidays').text)
    num_stations = int(xml_route.find('num_stns').text)
    stations = []
    for station in xml_route.find('config').findall('station'):
        stations.append(system.station_for_abbr(station.text))

    assert(len(stations) == num_stations)
    assert(stations[0] == origin or stations[1] == origin)
    assert(stations[-1] == dest or stations[-2] == dest)

    return name, abbr, route_id, origin, dest, direction, color, holidays, stations

def schedule_list():
    xml = call_xml_api("sched.aspx", cmd='scheds')
    xml_schedules = xml.find('schedules')
    schedules = []
    for xml_schedule in xml_schedules:
        id = int(xml_schedule.find('id').text)
        effective_date = parse_date_time(xml_schedule.find('effectivedate'))
        if effective_date < datetime.now(tz=tz.tzlocal()):
            schedules.append(schedule.Schedule(id, effective_date))
            
def schedule_origin_times(system, schedule_num=None, route_num=None):
    kwargs = {'cmd': 'routesched'}
    if schedule_num:
        kwargs['sched'] = schedule_num
    if route_num:
        kwargs['route'] = route_num
    xml = call_xml_api("sched.aspx", **kwargs)
    date = xml.find('date').text
    xml_route = xml.find('route')
    xml_trains = xml_route.findall('train')
    train_times = {}
    for xml_train in xml_trains:
        train_num = int(xml_train.get('index'))
        xml_stops = xml_train.findall('stop')

        stations_and_times = {}
        for stop in xml_stops:
            if stop.get('origTime'):
                station = system.station_for_abbr(stop.get('station'))
                date_time = parse_date_time("%s %s" % (date, stop.get('origTime')))
                if date_time.hour >= 12 and (date_time.hour <= 2 and date_time.minute < 27):
                    # correct for scheduled times past midnight
                    date_time = date_time + timedelta(days=1)
                stations_and_times[station] = date_time

        # { Station: DateTime }

        train_times[train_num] = stations_and_times

    # { 1: { Station: DateTime, Station2: DateTime }, 2: { Station: DateTime } }
    return train_times

def real_time_departures(system, station_name='ALL', direction=None):
    # Can't specify direction if station is set to ALL
    kwargs = {'cmd': 'etd'}
    if direction and station_name != 'ALL':
        kwargs['dir'] = direction[0:1].lower()
    kwargs['orig'] = station_name
    xml = call_xml_api("etd.aspx", **kwargs)
    timestamp = extract_xml_timestamp(xml)
    xml_stations = xml.findall('station')
    train_times = {}
    for xml_station in xml_stations:
        departing_station = system.station_for_abbr(xml_station.find('abbr').text)
        train_times[departing_station] = {}
        xml_destinations = xml_station.findall('etd')
        for xml_destination in xml_destinations:
            dest_station = system.station_for_abbr(xml_destination.find('abbreviation').text)
            train_times[departing_station][dest_station] = []
            xml_trains = xml_destination.findall('estimate')
            for xml_train in xml_trains:
                # TODO: Handle case when minutes might be 'Leaving'...sometimes lasts several mins at the end of the night
                countdown = int(str.replace(xml_train.find('minutes').text, 'Leaving', '0'))
                departure_time = parse_date_time(timestamp) + timedelta(minutes=countdown)
                platform = int(xml_train.find('platform').text)
                direction = xml_train.find('direction').text
                length = int(xml_train.find('length').text)

                train_times[departing_station][dest_station].append({'departure_time': departure_time,
                                                                     'platform': platform,
                                                                     'direction': direction.lower(),
                                                                     'length': length})
    return train_times
