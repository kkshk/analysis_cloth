"""
生成高仿真服装零售销售数据
特征：有盈利有亏损、有季节性、有品类成本差异、有真实折扣分布
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

# ========== 品类配置（模拟真实成本结构）==========
# cost_rate: 成本占售价比例。越高=利润越薄，越容易亏损
CATEGORIES = {
    "连衣裙": {"sub": ["A字裙", "吊带裙", "衬衫裙", "针织裙"], "cost": 0.42, "price_range": (199, 699)},
    "上衣": {"sub": ["T恤", "衬衫", "针织衫", "卫衣"], "cost": 0.38, "price_range": (89, 399)},
    "裤装": {"sub": ["牛仔裤", "休闲裤", "西装裤", "短裤"], "cost": 0.45, "price_range": (159, 599)},
    "外套": {"sub": ["羽绒服", "大衣", "夹克", "风衣"], "cost": 0.52, "price_range": (299, 1299)},
    "配饰": {"sub": ["围巾", "帽子", "包包", "腰带"], "cost": 0.30, "price_range": (39, 299)},
}

REGIONS = ["华东", "华南", "华北", "西南", "华中", "东北"]
COLORS = ["黑色", "白色", "米色", "藏青", "酒红", "灰色", "驼色", "墨绿"]
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
CUSTOMERS = [f"C{10000 + i}" for i in range(600)]


# 季节系数：1月/12月外套旺，5-8月连衣裙旺，过渡季上衣旺
def season_factor(month, category):
    if category == "外套":
        return {1: 2.0, 2: 1.5, 3: 1.0, 4: 0.6, 5: 0.4, 6: 0.3, 7: 0.3, 8: 0.4, 9: 0.7, 10: 1.4, 11: 1.9, 12: 2.2}.get(
            month, 1)
    if category == "连衣裙":
        return {1: 0.3, 2: 0.5, 3: 1.0, 4: 1.6, 5: 2.2, 6: 2.0, 7: 1.8, 8: 1.5, 9: 1.2, 10: 0.8, 11: 0.4, 12: 0.3}.get(
            month, 1)
    if category == "裤装":
        return {1: 1.5, 2: 1.3, 3: 1.1, 4: 1.0, 5: 0.9, 6: 0.8, 7: 0.8, 8: 0.9, 9: 1.0, 10: 1.2, 11: 1.4, 12: 1.6}.get(
            month, 1)
    return 1.0  # 上衣、配饰四季均衡


records = []
start_date = datetime(2024, 1, 1)
order_seq = 100000

# 生成约 2500 条订单
for _ in range(2600):
    cat = np.random.choice(list(CATEGORIES.keys()), p=[0.28, 0.30, 0.20, 0.12, 0.10])
    cfg = CATEGORIES[cat]
    sub = np.random.choice(cfg["sub"])
    base_cost = cfg["cost"]

    # 日期：偏重旺季
    month = np.random.choice(range(1, 13), p=[0.06, 0.06, 0.08, 0.10, 0.12, 0.10, 0.09, 0.09, 0.09, 0.10, 0.06, 0.05])
    day = np.random.randint(1, 28)
    order_date = datetime(2024, month, day) + timedelta(days=np.random.randint(0, 3))

    # 单价
    lo, hi = cfg["price_range"]
    unit_price = round(np.random.uniform(lo, hi), -1)
    quantity = np.random.choice([1, 1, 1, 2, 2, 3, 4], p=[0.4, 0.25, 0.15, 0.1, 0.05, 0.03, 0.02])

    # 折扣：大部分正价，促销有分布（制造亏损的关键）
    disc = np.random.choice(
        [1.0, 0.95, 0.9, 0.85, 0.8, 0.7, 0.6, 0.5],
        p=[0.45, 0.20, 0.15, 0.08, 0.06, 0.03, 0.02, 0.01]
    )
    discount_rate = round(disc * 100)

    # 实际成交价
    actual_price = unit_price * disc
    total_sales = round(actual_price * quantity, 2)

    # 成本：西装裤/外套成本高，加随机波动。过季清仓（高折扣）成本不降，容易亏损
    cost_rate = base_cost + np.random.uniform(-0.05, 0.08)
    cost = total_sales * cost_rate

    # 利润 = 销售额 - 成本 - 平台/渠道费用
    channel_fee = total_sales * np.random.uniform(0, 0.03)
    profit = round(total_sales - cost - channel_fee, 2)

    order_seq += 1
    region = np.random.choice(REGIONS)
    color = np.random.choice(COLORS)
    size = np.random.choice(SIZES, p=[0.05, 0.15, 0.30, 0.25, 0.15, 0.10])
    customer = np.random.choice(CUSTOMERS)

    records.append({
        "订单号": f"DD{order_seq}",
        "订单日期": order_date.strftime("%Y-%m-%d"),
        "月份": month,
        "类别": cat,
        "子类别": sub,
        "单价": unit_price,
        "数量": quantity,
        "总销售额": total_sales,
        "折扣率": discount_rate,
        "利润": profit,
        "地区": region,
        "颜色": color,
        "尺码": size,
        "客户ID": customer,
    })

df = pd.DataFrame(records)

# 加上利润率列
df["利润率"] = (df["利润"] / df["总销售额"] * 100).round(2)

# 打乱顺序
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

df.to_csv("fashion_sales_realistic.csv", index=False, encoding="utf-8-sig")
print(f"✅ 生成 {len(df)} 条数据")
print(f"📊 亏损订单数：{len(df[df['利润'] < 0])} 条（占比 {len(df[df['利润'] < 0]) / len(df) * 100:.1f}%）")
print(f"📈 平均利润率：{df['利润率'].mean():.1f}%")
print(f"💰 总销售额：¥{df['总销售额'].sum():,.0f}")
print(f"📉 总利润：¥{df['利润'].sum():,.0f}")
print("\n各子类别盈亏情况：")
print(df.groupby('子类别').agg(订单数=('利润', 'count'), 总利润=('利润', 'sum'),
                               平均利润率=('利润率', 'mean')).sort_values('总利润'))