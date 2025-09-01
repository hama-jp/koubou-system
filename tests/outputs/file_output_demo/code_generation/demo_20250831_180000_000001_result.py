# Code Generation Result
# Task ID: demo_20250831_180000_000001
# Generated: 20250831_180104
# Success: True

def calculate_fibonacci(n):
    """
    フィボナッチ数列のn番目の値を計算します
    
    Args:
        n (int): 計算する番目（0から開始）
        
    Returns:
        int: フィボナッチ数列のn番目の値
        
    Raises:
        ValueError: nが負の数の場合
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    
    if n <= 1:
        return n
    
    try:
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b
    except Exception as e:
        print(f"Error calculating fibonacci: {e}")
        raise