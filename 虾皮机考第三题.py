# 反转字符串中的小写字母,并且保持单个单词的顺序不变,其他字符的位置不变
# 字符串中包含大写字母,小写字母,数字和空格
# 输入:"Shopee is our family 123"->输出:"Seepoh si ruo ylimaf 123"
def solve(s):
    s = list(s)
    n = len(s)
    start = 0
    while start<=n-1:
        # 1.遇到空格就跳过
        if s[start] == ' ':
            start += 1
            continue

        # 2.找到单词的右边界:start和end之间无空格,end == n - 1或者end的下一个是空格
        end = start
        while end <= n - 1 and s[end] != ' ':
            end += 1
        left = start
        right = end - 1
        while left < right:
            # 找小写字母
            while left < right and not s[left].islower():
                left += 1

            while left < right and not s[right].islower():
                right -= 1

            if left < right:
                s[left],s[right] = s[right],s[left]
                left += 1
                right -= 1
        start = end
    return ''.join(s)

s = "Shopee is our family 123"
print(solve(s))     