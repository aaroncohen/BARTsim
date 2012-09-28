import logging
import datetime
import time

import bart_api
from segment import Segment
from train import Train
from utils import window


DWELL_TIME = datetime.timedelta(seconds=30)

class TrainSystem:
    """
    Oversees the train system as a whole.
    """

    def __init__(self):
        self.stations = bart_api.station_list(self)
        self.routes = bart_api.route_list(self)
        self.segments = []
        self.generate_segments()
#        self.schedule = Schedule()
        self.real_departures = {}
        self.trains = []
        self.create_trains()
        logging.info("Created TrainSystem. %d stations, %d routes, %d segments, %d mi of track, %d trains."\
                    % (len(self.stations), len(self.routes), len(self.segments), self.segments_distance(self.segments), len(self.trains)))

    def update_real_departures(self):
        self.real_departures = bart_api.real_time_departures(self)

    def generate_segments(self):
        logging.debug("Generating segments. %d existing already." % len(self.segments))
        # TODO: time estimates for segments
        for route in self.routes:
            logging.debug("Walking route %s" % repr(route))
            for station_a, station_b in window(route.stations):
                est_time = self.calc_segment_time(station_a, station_b)
                if station_a.lat < station_b.lat: # No stations share equal lats, higher lats mean northern
                    new_segment = Segment(station_b, station_a, est_time, self)
                else:
                    new_segment = Segment(station_a, station_b, est_time, self)

                if new_segment in self.segments:  # If a matching segment already exists, use that
                    new_segment = self.segments[self.segments.index(new_segment)]

                logging.debug("\tSegment: %s" % repr(new_segment))

                for station in (station_a, station_b):
                    station.add_containing_segment(new_segment)

                if not new_segment in route.segments:
                    route.segments.append(new_segment)

                if not new_segment in self.segments:
                    self.segments.append(new_segment)

            logging.debug("\tRoute contains %d segments" % len(route.segments))
        logging.debug("Segment generation complete. %d total segments, %d unique" % (len(self.segments), len(set(self.segments))))

    def calc_segment_time(self, station_a, station_b):
        #find all uses of segment, average
        deltas = []
        for route in self.routes:
            for i in range(1, len(route.origin_times)+1):
                origin_times = route.origin_times[i]
                if not station_a in origin_times or not station_b in origin_times:
                    continue
                time_a = origin_times[station_a]
                time_b = origin_times[station_b]
                if time_a > time_b:
                    delta = time_a - time_b
                else:
                    delta = time_b - time_a
                if time_a.day == time_b.day: # prevent deltas that cross midnight from screwing things up
                    deltas.append(delta - DWELL_TIME)
        return sum(deltas, datetime.timedelta(0)) / len(deltas)

    def create_trains(self):
        logging.debug("Creating trains for %d routes" % len(self.routes))
        self.trains = []
        for route in self.routes:
            for i in range(1, len(route.origin_times)+1):
                origin_times = route.origin_times[i]
                self.trains.append(
                    Train(i, origin_times, route, self)
                )
        logging.debug("Created %d trains, %d scheduled active" % (len(self.trains),
                                                                  len([train for train in self.trains if train.scheduled_active()])))

    def station_for_abbr(self, station_abbr):
        """
        Returns a station object given a station abbreviation. If no matching station is found, returns None.
        """
        for station in self.stations:
            if station.abbr == station_abbr:
                return station
        return None

    def route_for_long_id(self, long_id):
        for route in self.routes:
            if route.long_id == long_id:
                return route
        return None

    def find_transfer_stations(self, origin_route, dest_route, origin_station=None, dest_station=None):
        assert(origin_station in origin_route.stations)
        assert(dest_station in dest_route.stations)

        origin_station_index = origin_route.stations.index(origin_station)
        usable_origin_route_stations = origin_route.stations[origin_station_index:]

        dest_station_index = dest_route.stations.index(dest_station)
        usable_dest_route_stations = dest_route.stations[:dest_station_index]

        return set(usable_origin_route_stations) & set(usable_dest_route_stations)

    def segments_distance(self, segments):
        return sum([segment.length for segment in segments])

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    system = TrainSystem()
    while True:
        # TODO: Determining active trains by the schedule doesn't cut it
        active_trains = [train for train in system.trains if train.scheduled_active()]
        for train in active_trains:
            system.update_real_departures()
            train.update_progress()
        time.sleep(20)
    logging.shutdown()