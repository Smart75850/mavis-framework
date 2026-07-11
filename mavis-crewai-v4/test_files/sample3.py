def calculate(x, y, op):
    """
    根据指定的运算符对两个数进行四则运算。

    参数:
        x (float): 第一个操作数（被加数/被减数/被乘数/被除数）。
        y (float): 第二个操作数（加数/减数/乘数/除数）。
        op (str): 运算符，支持以下四种字符串值:
                  - "add": 加法运算
                  - "sub": 减法运算
                  - "mul": 乘法运算
                  - "div": 除法运算

    返回:
        float: 当运算符为 "add"、"sub"、"mul" 时，返回对应运算结果（浮点数）。
               当运算符为 "div" 时，返回 x 除以 y 的结果，结果保留两位小数。
        None:  当运算符为 "div" 且 y 为 0 时，打印错误信息并返回 None。
               当 op 参数为未知运算符时，返回 None。
    """
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