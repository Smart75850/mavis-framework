def hello(name: str) -> str:
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    return a + b

def greet_user() -> None:
    user_name: str = input("Please enter your name: ")
    print(hello(user_name))
    age: int = int(input("How old are you? "))
    year_of_birth: int = 2023 - age
    print(f"You were born in {year_of_birth}.")
    
    # 新增：计算用户的生肖年份及其代表的动物
    chinese_zodiac_start_year: int = 1900  # 起始年为猴年对应的公元纪年
    chinese_zodiac_years: list[str] = ['Monkey', 'Rooster', 'Dog', 'Pig', 'Rat', 'Ox', 'Tiger', 'Rabbit', 'Dragon', 'Snake', 'Horse', 'Sheep']
    
    # 计算对应的生肖
    zodiac_year_index: int = (year_of_birth - chinese_zodiac_start_year) % 12
    zodiac_year_animal: str = chinese_zodiac_years[zodiac_year_index]
    print(f"Your Chinese Zodiac Year is the {zodiac_year_animal}.")
    
    # 新增：问候用户
    print("Hope you have a great day!")

if __name__ == "__main__":
    greet_user()
    print(add(1, 2))