class User:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def greet(self):
        return f"Hi, I'm {self.name}, {self.age} years old"

    def update_age(self, new_age):
        if isinstance(new_age, int) and new_age >= 0:
            self.age = new_age
        else:
            raise ValueError("Age must be a non-negative integer")

# Example usage of the User class
if __name__ == "__main__":
    user1 = User("Alice", 30)
    print(user1.greet())
    
    try:
        user1.update_age(35)
        print(user1.greet())

        user1.update_age(-20)  # This should raise a ValueError
        print(user1.greet())   # Should not reach this line
    except Exception as e:
        print(e)