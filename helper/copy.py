def Object(obj):
    if isinstance(obj, dict):
        result = Dict(obj)
    elif isinstance(obj, list):
        result = List(obj)
    else:
        result = obj

    return result

def Dict(obj):
    result = obj.copy()

    for key, value in obj.items():
        if isinstance(value, dict):
            result[key] = Dict(value)
        elif isinstance(value, list):
            result[key] = List(value)

    return result

def List(obj):
    result = obj.copy()

    for index, value in enumerate(obj):
        if isinstance(value, dict):
            result[index] = Dict(value)
        elif isinstance(value, list):
            result[index] = List(value)

    return result
