def process_data(data):
    """Process the input data by filtering and transforming it."""
    result = []
    for item in data:
        if item > 0:  # Only consider positive numbers
            result.append(item * 2)
    return result

# New function to test negative values as well
def process_negative_data(data):
    """Process the input data including negative numbers by filtering and transforming it."""
    result = []
    for item in data:
        if item < 0:  # Consider only negative numbers
            result.append(item * -2)
        elif item == 0:  # Add zero handling
            result.append(0)
    return result

# Example usage of both functions
if __name__ == "__main__":
    sample_data = [1, -2, 3, -4, -6, 5, 0]
    print("Positive values processed:", process_data(sample_data))
    print("Negative and zero values processed:", process_negative_data(sample_data))