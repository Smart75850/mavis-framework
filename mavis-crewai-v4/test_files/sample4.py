# 定义一个函数,用于处理输入数据
def process_data(data):
    """Process the input data by filtering and transforming it."""  # 函数文档字符串,说明该函数用于处理输入数据,通过过滤和转换的方式
    result = []  # 初始化一个空列表,用于存储处理后的结果
    for item in data:  # 遍历输入数据中的每一个元素
        if item > 0:  # 仅考虑正数,过滤掉非正数的元素
            result.append(item * 2)  # 将正数元素乘以 2 后,添加到结果列表中
    return result  # 返回处理后的结果列表

# 新增一个函数,用于测试负数值的处理
def process_negative_data(data):
    """Process the input data including negative numbers by filtering and transforming it."""  # 函数文档字符串,说明该函数用于处理包含负数的输入数据,同样通过过滤和转换的方式
    result = []  # 初始化一个空列表,用于存储处理后的结果
    for item in data:  # 遍历输入数据中的每一个元素
        if item < 0:  # 考虑仅处理负数
            result.append(item * -2)  # 将负数元素乘以 -2(实际是取绝对值再乘以 2)后,添加到结果列表中
        elif item == 0:  # 如果元素等于 0,则进行特殊处理
            result.append(0)  # 将 0 直接添加到结果列表中
    return result  # 返回处理后的结果列表

# 示例使用两个函数的部分
if __name__ == "__main__":  # 判断该模块是否作为主程序直接运行,如果是则执行下面的代码
    sample_data = [1, -2, 3, -4, -6, 5, 0]  # 定义一个示例数据列表,包含正数、负数和零
    print("Positive values processed:", process_data(sample_data))  # 打印处理正数的结果,调用 process_data 函数
    print("Negative and zero values processed:", process_negative_data(sample_data))  # 打印处理负数和零的结果,调用 process_negative_data 函数