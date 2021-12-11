schema = {
    "event": {
        "attributes": ["name", "date_start", "date_end"],
        "key": "name",
        "representation": ["name", "date_start"]
    },
    "person": {
        "attributes": ["name", "gender"],
        "key": "name",
        "representation": ["name", "gender"]
    },
    "university": {
        "attributes": ["name"],
        "key": "name",
        "representation": "name"
    },
    "place": {
        "attributes": ["location"],
        "key": "location",
        "representation": "location"
    }
}
