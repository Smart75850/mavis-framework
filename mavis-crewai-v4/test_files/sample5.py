class User:
    def __init__(self, name: str, age: int) -> None:
        # 初始化用户姓名和年龄
        self.name: str = name
        self.age: int = age

    def greet(self) -> str:
        # 返回问候语字符串
        return f"Hi, I'm {self.name}, {self.age} years old"

    def update_age(self, new_age: int) -> None:
        # 更新年龄,验证输入合法性
        if isinstance(new_age, int) and new_age >= 0:
            self.age = new_age
        else:
            raise ValueError("Age must be a non-negative integer")

# User 类的示例用法
if __name__ == "__main__":
    user1 = User("Alice", 30)
    print(user1.greet())
    
    try:
        user1.update_age(35)
        print(user1.greet())

        user1.update_age(-20)  # 这行应该会引发 ValueError
        print(user1.greet())   # 不应执行到这一行
    except Exception as e:
        print(e)