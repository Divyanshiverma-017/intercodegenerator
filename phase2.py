temp_count = 0


class Node:
    """Simple binary tree node: operator or identifier in value; optional left/right children."""

    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right


def new_temp():
    global temp_count
    temp_count += 1
    return f"t{temp_count}"


tac = []  # stores three address code

def generate_TAC(node):
    # If leaf node (operand)
    if node.left is None and node.right is None:
        return node.value
    
    # Recursively process left and right
    left = generate_TAC(node.left)
    right = generate_TAC(node.right)
    
    temp = new_temp()
    tac.append(f"{temp} = {left} {node.value} {right}")
    
    return temp