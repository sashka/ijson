class JSONError(Exception):
    pass

class IncompleteJSONError(JSONError):
    def __init__(self):
        super(IncompleteJSONError, self).__init__('Incomplete or empty JSON data')
