from phase2 import tac

quadruples = []


def generate_quadruples():
    for line in tac:
        parts = line.split()
        if len(parts) == 3 and parts[1] == "=":
            # e.g. a = t1
            result, _, src = parts
            quadruples.append(("MOV", src, "", result))
            continue
        result = parts[0]
        arg1 = parts[2]
        op = parts[3]
        arg2 = parts[4]
        quadruples.append((op, arg1, arg2, result))