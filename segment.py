import utils

class Segment:
    def __init__(self, n_station, s_station, time, system, directionality=None):
        self.n_station = n_station
        self.s_station = s_station
        self.stations = [n_station, s_station]
        self.length = self.calc_length()
        self.time = time
        self.system = system
        self.directionality = directionality
        self.trains = None

        assert self.n_station.lat > self.s_station.lat

    def current_trains(self, direction='both'):
        if direction == 'both':
            return self.trains
        else:
            return [train for train in self.trains if train.direction == direction]

    def calc_length(self):
        return utils.haversine(self.n_station.lng, self.n_station.lat, self.s_station.lng, self.s_station.lat)

    def __eq__(self, other):
        # Only compare Segments based on their stations...direction matters though
        if isinstance(other, self.__class__):
            return self.n_station == other.n_station and self.s_station == other.s_station
        else:
            return False

    def __hash__(self):
        return hash((self.n_station, self.s_station))

    def __repr__(self):
        return "<Segment: N %s - S %s>" % (self.n_station, self.s_station)