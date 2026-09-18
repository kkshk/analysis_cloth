import os
import pandas as pd


class FashionAnalyzer:
    def __init__(self, file_path=None):
        if file_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, 'fashion_sales_realistic.csv')
        elif not os.path.isabs(file_path):
            # 如果传的是相对路径，就基于本文件所在目录来解析
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, file_path)

        self.df = pd.read_csv(file_path, encoding='utf-8-sig')
        self.df['订单日期'] = pd.to_datetime(self.df['订单日期'])
        self.df['月份'] = self.df['订单日期'].dt.month
        self.df['利润率'] = (self.df['利润'] / self.df['总销售额'] * 100).round(2)

    def get_kpis(self, region=None, category=None):
        df_filtered = self.df
        if region:
            df_filtered = df_filtered[df_filtered['地区'] == region]
        if category:
            df_filtered = df_filtered[df_filtered['类别'] == category]

        total_sales = df_filtered['总销售额'].sum()
        total_profit = df_filtered['利润'].sum()
        avg_price = df_filtered['总销售额'].mean() if len(df_filtered) > 0 else 0
        return total_sales, total_profit, avg_price

    def get_sales_by_category(self):
        return self.df.groupby('类别')['总销售额'].sum().reset_index()

    def get_monthly_trend(self):
        return self.df.groupby('月份')['总销售额'].sum().reset_index()

    def get_profit_ranking(self):
        return self.df.groupby('子类别')['利润'].sum().sort_values(ascending=False)

    def get_color_size_preference(self):
        color_sales = self.df.groupby('颜色')['总销售额'].sum()
        size_sales = self.df.groupby('尺码')['数量'].sum()
        return color_sales, size_sales