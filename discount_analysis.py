"""
折扣分析引擎 - 三层分析架构（修复版）
"""

import pandas as pd
import numpy as np


class DiscountAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.has_data = False
        self.message = ""
        self._prepare_data()

    def _prepare_data(self):
        discount_col = None
        for col in ['折扣', '折扣率', 'discount', 'Discount']:
            if col in self.df.columns:
                discount_col = col
                break

        if discount_col is None:
            self.message = "数据中未找到折扣字段"
            return

        self.has_data = True
        self.df['_discount_rate'] = self.df[discount_col]

        if self.df['_discount_rate'].max() > 1:
            self.df['_discount_rate'] = self.df['_discount_rate'] / 100

        if '利润率' not in self.df.columns:
            self.df['利润率'] = (
                self.df['利润'] / self.df['总销售额'].replace(0, np.nan) * 100
            ).replace([np.inf, -np.inf], np.nan).fillna(0)

        self.df['_discount_pct'] = (self.df['_discount_rate'] * 100).round(0)

    # ========== 第一层 ==========
    def analyze_overview(self):
        if not self.has_data:
            return {"has_data": False, "message": self.message}

        df_valid = self.df.dropna(subset=['_discount_rate', '利润率'])
        if len(df_valid) < 3:
            return {"has_data": True, "sample_count": len(df_valid), "summary": f"样本仅 {len(df_valid)} 条，需要至少3条"}

        corr = df_valid['_discount_rate'].corr(df_valid['利润率'])

        x = df_valid['_discount_rate']
        y = df_valid['利润率']
        n = len(x)
        if n * (x**2).sum() - (x.sum())**2 == 0:
            slope = 0
        else:
            slope = (n * (x * y).sum() - x.sum() * y.sum()) / (n * (x**2).sum() - (x.sum())**2)
        intercept = y.mean() - slope * x.mean()

        # 分组
        try:
            df_valid['_bin'] = pd.cut(df_valid['_discount_rate'], bins=min(10, len(df_valid)//2+1), include_lowest=True)
            bin_summary = df_valid.groupby('_bin', observed=True).agg(
                平均利润率=('利润率', 'mean'),
                订单数=('利润率', 'count')
            ).reset_index()
            bin_summary['_bin'] = bin_summary['_bin'].astype(str)
        except Exception:
            bin_summary = pd.DataFrame()

        return {
            "has_data": True,
            "sample_count": len(df_valid),
            "correlation": round(corr, 3),
            "slope": round(slope, 2),
            "intercept": round(intercept, 2),
            "bin_summary": bin_summary if len(bin_summary) > 0 else None,
            "summary": f"折扣与利润率相关系数 {corr:.3f}，折扣每降低10%利润率{'下降' if slope < 0 else '上升'} {abs(slope * 0.1):.1f}%"
        }

    # ========== 第二层 ==========
    def analyze_break_even(self):
        if not self.has_data:
            return {"has_data": False, "message": self.message}

        results = []

        # 检查子类别列
        if '子类别' not in self.df.columns:
            return {"has_data": False, "message": "数据中未找到'子类别'列"}

        for sub_cat in self.df['子类别'].unique():
            sub_data = self.df[self.df['子类别'] == sub_cat]

            if len(sub_data) < 2:  # 从3降到2，更宽松
                continue

            grouped = sub_data.groupby('_discount_pct').agg(
                平均利润率=('利润率', 'mean'),
                订单数=('利润率', 'count')
            ).reset_index()

            if len(grouped) < 1:
                continue

            # 找盈亏平衡点
            profit_groups = grouped[grouped['平均利润率'] > 0]
            if len(profit_groups) > 0:
                break_even = profit_groups['_discount_pct'].min()
            else:
                # 如果全部亏损，用最大利润率对应的折扣
                break_even = grouped.loc[grouped['平均利润率'].idxmax(), '_discount_pct']

            full_price = sub_data[sub_data['_discount_pct'] >= 95]
            if len(full_price) > 0:
                full_margin = full_price['利润率'].mean()
            else:
                full_margin = sub_data['利润率'].mean()

            results.append({
                "sub_category": str(sub_cat),
                "break_even_discount": float(break_even),
                "full_price_margin": round(float(full_margin), 1),
                "sample_count": len(sub_data),
                "all_bins": grouped.to_dict('records')
            })

        if not results:
            return {
                "has_data": True,
                "items": [],
                "summary": "每个子类别数据不足（需要至少2条），无法计算盈亏线"
            }

        results.sort(key=lambda x: x['break_even_discount'], reverse=True)

        return {
            "has_data": True,
            "items": results,
            "summary": f"共分析 {len(results)} 个品类，{results[0]['sub_category']} 盈亏线最高（{results[0]['break_even_discount']:.0f}%）"
        }

    # ========== 第三层 ==========
    def analyze_decision(self):
        if not self.has_data:
            return {"has_data": False, "message": self.message}

        bins = [0, 55, 65, 75, 85, 95, 101]
        labels = ['≤55折', '55-65折', '65-75折', '75-85折', '85-95折', '95-100折']

        self.df['_discount_bin'] = pd.cut(
            self.df['_discount_pct'], bins=bins, labels=labels, include_lowest=True
        )

        decision_df = self.df.groupby('_discount_bin', observed=True).agg(
            总销售额=('总销售额', 'sum'),
            总利润=('利润', 'sum'),
            总销量=('数量', 'sum'),
            订单数=('利润率', 'count')
        ).reset_index()

        if len(decision_df) < 2:
            return {"has_data": True, "summary": "折扣区间数据不足"}

        max_profit_row = decision_df.loc[decision_df['总利润'].idxmax()]
        best_bin = max_profit_row['_discount_bin']
        max_profit = max_profit_row['总利润']
        max_volume = max_profit_row['总销量']

        fp_row = decision_df[decision_df['_discount_bin'] == '95-100折']
        if len(fp_row) > 0:
            fp_profit = fp_row['总利润'].values[0]
            fp_volume = fp_row['总销量'].values[0]
        else:
            fp_profit = 0
            fp_volume = 0

        if fp_volume > 0:
            volume_lift = (max_volume - fp_volume) / fp_volume * 100
        else:
            volume_lift = 0

        profit_diff = max_profit - fp_profit
        profit_diff_pct = (profit_diff / fp_profit * 100) if fp_profit > 0 else 0

        return {
            "has_data": True,
            "interval_data": decision_df.to_dict('records'),
            "best_bin": str(best_bin),
            "max_total_profit": float(max_profit),
            "full_price_profit": float(fp_profit),
            "volume_lift_pct": round(volume_lift, 1),
            "profit_diff": float(profit_diff),
            "profit_diff_pct": round(profit_diff_pct, 1),
            "summary": f"最优折扣区间为 {best_bin}，总利润 ¥{max_profit:,.0f}"
        }

    def run_all(self):
        return {
            "overview": self.analyze_overview(),
            "break_even": self.analyze_break_even(),
            "decision": self.analyze_decision()
        }