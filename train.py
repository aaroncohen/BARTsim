from datetime import datetime, timedelta
import logging
from station import Station
from utils import window
import utils

DWELL_TIME = timedelta(seconds=30)

class Train:
    def __init__(self, id, scheduled_departures, route, num_cars):
        self.id = id
        self.scheduled_departures = scheduled_departures
        self.route = route
        self.num_cars = num_cars

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
            next_stop = self.route.stations[curr_index + 1]
        else:
            segment = curr_location
            curr_index = self.route.segments.index(segment)
            next_segment = self.route.segments[curr_index + 1]
            next_stop = (set(segment) & set(next_segment))[0] # intersection
        return next_stop

    def update_scheduled_location(self):
        if self.scheduled_active():
            for station_a, station_b in window(self.stops):
                now = datetime.now()
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
        elif self.scheduled_ended():
            logging.info("%s has reached the end of the line." % repr(self))
            self.scheduled_location = self.destination
            self.scheduled_location_progress = 1.0

    def update_real_location(self):
        pass

    def update_progress(self):
        self.update_scheduled_location()
        self.update_real_location()
        pass

    def __repr__(self):
        return "<Train: %s-%s, %d cars, %s>" % (self.origin.abbr, self.destination.abbr,
                                                self.num_cars, self.origin_time.time())