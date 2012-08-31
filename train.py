from datetime import datetime, timedelta
import logging
from station import Station
from utils import window
import utils

DWELL_TIME = timedelta(seconds=30)

class Train:
    def __init__(self, id, scheduled_departures, route, system):
        self.id = id
        self.scheduled_departures = scheduled_departures
        self.route = route
        self.system = system

        self.num_cars = 0
        self.stops = [station for station in self.route.stations if station in self.scheduled_departures.keys()]
        self.origin = self.stops[0]
        self.destination = self.stops[-1]
        self.origin_time = self.scheduled_departures[self.origin]
        self.destination_time = self.scheduled_departures[self.destination]

        self.real_location = self.scheduled_location = self.origin # Either a station or a segment
        self.real_location_progress = self.scheduled_location_progress = 0.0 # 0.0 - 1.0 percentage...either traveled over a segment, or progress through station dwell time
        self.real_location_remaining = self.scheduled_location_remaining = timedelta(0)

        self.schedule_offsets = []

    def scheduled_active(self):
        return not(self.scheduled_not_yet_started() or self.scheduled_ended())

    def scheduled_not_yet_started(self):
        now = datetime.now()
        return now <= (self.origin_time - DWELL_TIME)

    def scheduled_ended(self):
        now = datetime.now()
        return now >= (self.destination_time + DWELL_TIME)

    def direction(self, curr_location):
        next_stop = self.next_stop(curr_location)
        if curr_location.__class__ == Station:
            segment = curr_location.segment_to_station(next_stop)
        else:
            segment = curr_location

        if segment.n_station == next_stop:
            return 'north'
        elif segment.s_station == next_stop:
            return 'south'

    def scheduled_departure_for_station(self, station):
        return self.scheduled_departures[station]

    def next_stop(self, curr_location):
        if curr_location.__class__ == Station:
            curr_index = self.route.stations.index(curr_location)
            if curr_index + 1 >= len(self.route.stations):
                next_stop = None
            else:
                next_stop = self.route.stations[curr_index + 1]
        else:
            segment = curr_location
            curr_index = self.route.segments.index(segment)
            if curr_index + 1 >= len(self.route.segments): # End of the line
                next_stop = None
            else:
                next_segment = self.route.segments[curr_index + 1]
                next_stop = list(set(segment.stations) & set(next_segment.stations))[0] # intersection
        return next_stop

    def previous_stop(self, curr_location):
        if curr_location.__class__ == Station:
            curr_index = self.route.stations.index(curr_location)
            if curr_index - 1 < 0:
                prev_stop = None
            else:
                prev_stop = self.route.stations[curr_index - 1]
        else:
            segment = curr_location
            curr_index = self.route.segments.index(segment)
            if curr_index - 1 < 0: # Beginning of the line
                prev_stop = None
            else:
                next_segment = self.route.segments[curr_index - 1]
                prev_stop = list(set(segment.stations) & set(next_segment.stations))[0] # intersection
        return prev_stop

    def earlier_train(self):
        prev_index = self.system.trains.index(self)+1
        if not prev_index < 0:
            return self.system.trains[prev_index]
        else:
            return None

    def later_train(self):
        next_index = self.system.trains.index(self)+1
        if not next_index > len(self.system.trains):
            return self.system.trains[next_index]
        else:
            return None

    def update_scheduled_location(self):
        now = datetime.now()
        if self.scheduled_active():
            for station_a, station_b in window(self.stops):
                station_a_dept_time = self.scheduled_departures[station_a]
                if now >= station_a_dept_time:
                    station_b_dept_time = self.scheduled_departures[station_b]
                    station_b_arrv_time = station_b_dept_time - DWELL_TIME
                    if now >= station_b_arrv_time and now < station_b_dept_time:
                        self.scheduled_location = station_b
                        self.scheduled_location_progress = utils.time_range_progress(station_b_arrv_time, station_b_dept_time, now)
                        self.scheduled_location_remaining = station_b_dept_time - now
                        logging.info("Train %s is waiting at %s" % (repr(self), repr(station_b)))
                        break
                    elif now >= station_a_dept_time and now < station_b_arrv_time:
                        self.scheduled_location = station_a.segment_to_station(station_b)
                        self.scheduled_location_progress = utils.time_range_progress(station_a_dept_time, station_b_arrv_time, now)
                        self.scheduled_location_remaining = station_b_arrv_time - now
                        logging.info("%s is %s from %s" % (repr(self), str(self.scheduled_location_remaining), repr(station_b)))
                        break
        elif self.scheduled_not_yet_started():
            self.scheduled_location = self.origin
            self.scheduled_location_progress = 0.0
            self.scheduled_location_remaining = self.scheduled_departure_for_station(self.origin) - now
        elif self.scheduled_ended():
            logging.info("%s has reached the end of the line." % repr(self))
            self.scheduled_location = self.destination
            self.scheduled_location_progress = 1.0
            self.scheduled_location_remaining = timedelta(seconds=0)

    def update_real_location(self):
        now = datetime.now()
        departures = self.system.real_departures
        next_station = self.next_stop(self.scheduled_location)
        stations_to_check = []
        if next_station: # might be end of line
            stations_to_check.append(next_station)
        if self.scheduled_location.__class__ == Station:
            stations_to_check.append(self.scheduled_location)

        if len(stations_to_check) < 1:
            #end of line
            self.real_location = self.destination
            self.real_location_progress = 1.0
            self.real_location_remaining = timedelta(seconds=0)

        likely_matches = []

        for station_to_check in stations_to_check:
        # Search backwards for likely match (direction, destination, time, known length)
            if station_to_check in departures and self.destination in departures[station_to_check]:
                possible_trains = departures[station_to_check][self.destination]
            else:
                possible_trains = []
            for train in possible_trains:
                if not train['direction'] == self.direction(self.scheduled_location):
                    continue
                if self.num_cars > 0 and train['length'] != self.num_cars:
                    continue # this may screw things up if a wrong train gets matched at some point
                likely_matches.append(train)

            scheduled_departure = self.scheduled_departure_for_station(station_to_check)
            # when match is decided, set values
            for match in likely_matches:
                # filter out if more than a minute early
                if match['departure_time'] < scheduled_departure - DWELL_TIME - timedelta(minutes=1):
                    continue
                else:
                    arrival_time = match['departure_time'] - DWELL_TIME
                    if now > arrival_time and now <= match['departure_time']:
                        self.real_location = station_to_check
                        self.real_location_progress = utils.time_range_progress(arrival_time, match['departure_time'], now)
                        self.real_location_remaining = match['departure_time'] - now - DWELL_TIME
                    elif now < arrival_time: # must be in previous segment
                        prev_station = self.previous_stop(station_to_check)
                        self.real_location = prev_station.segment_to_station(station_to_check)
                        segment_total_time = self.real_location.time
                        departure_time = arrival_time - segment_total_time
                        self.real_location_progress = utils.time_range_progress(departure_time, arrival_time, now)
                        self.real_location_remaining = arrival_time - now
                    break

    def update_progress(self):
        self.update_scheduled_location()
        self.update_real_location()
        pass

    def __repr__(self):
        return "<Train: %s-%s, %d cars, %s>" % (self.origin.abbr, self.destination.abbr,
                                                self.num_cars, self.origin_time.time())