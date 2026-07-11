def calculate(x, y, op):
    if op == "add":
        return x + y
    elif op == "sub":
        return x - y
    elif op == "mul":
        return x * y
    elif op == "div":
        # 添加异常处理，防止除数为零的情况
        try:
            result = x / y
        except ZeroDivisionError:
            print("Error: Division by zero is not allowed.")
            return None
        else:
            return round(result, 2)  # 结果保留两位小数
    return None

# 示例测试用例
if __name__ == "__main__":
    print(calculate(10, 5, "add"))  # 输出应为 15.00，为了格式统一
    print(calculate(10, 5, "sub"))  # 输出应为 5.00
    print(calculate(10, 5, "mul"))  # 输出应为 50.00
    print(calculate(10, 5, "div"))  # 输出应为 2.00
    print(calculate(10, 0, "div"))  # 输出应为 错误信息和 None，为了格式统一