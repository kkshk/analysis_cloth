"""
PDF 报告生成器 v3.0 - 基于 reportlab，彻底解决中文宽度问题
依赖：pip install reportlab kaleido
"""

import os
import tempfile
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor
from datetime import datetime


class ReportGenerator:
    def __init__(self, df: pd.DataFrame, df_filtered: pd.DataFrame,
                 category: str = "全部", region: str = "全部"):
        self.df = df
        self.d = df_filtered.copy()
        self.category = category
        self.region = region
        self.tmpdir = tempfile.mkdtemp()
        self.chart_files = []

    def _save_chart(self, fig, name):
        path = os.path.join(self.tmpdir, f"{name}.png")
        try:
            fig.write_image(path, width=900, height=420, scale=2)
            self.chart_files.append(path)
            return path
        except Exception as e:
            print(f"图表导出失败 {name}: {e}")
            return None

    def _cleanup(self):
        for f in self.chart_files:
            try:
                os.remove(f)
            except Exception:
                pass
        try:
            os.rmdir(self.tmpdir)
        except Exception:
            pass

    def _gen_charts(self):
        charts = {}
        if len(self.d) == 0:
            return charts

        cat = self.d.groupby('类别', as_index=False)['总销售额'].sum().sort_values('总销售额', ascending=False)
        if len(cat) > 0:
            fig = px.bar(cat, x='类别', y='总销售额', color='总销售额', color_continuous_scale='Blues')
            p = self._save_chart(fig, "cat")
            if p: charts['cat'] = p

        if '月份' in self.d.columns:
            mon = self.d.groupby('月份', as_index=False)['总销售额'].sum().sort_values('月份')
            fig = px.line(mon, x='月份', y='总销售额', markers=True, line_shape='spline')
            fig.update_traces(line=dict(width=3, color='#FF4B4B'))
            p = self._save_chart(fig, "mon")
            if p: charts['mon'] = p

        pr = self.d.groupby('子类别', as_index=False)['利润'].sum().sort_values('利润')
        colors_bar = ['#FF4B4B' if v < 0 else '#00CC96' for v in pr['利润']]
        fig = go.Figure(go.Bar(x=pr['利润'], y=pr['子类别'], orientation='h', marker_color=colors_bar))
        p = self._save_chart(fig, "profit")
        if p: charts['profit'] = p

        if '地区' in self.d.columns:
            rg = self.d.groupby('地区', as_index=False).agg(总销售额=('总销售额', 'sum'), 利润=('利润', 'sum'))
            fig = px.scatter(rg, x='总销售额', y='利润', size='总销售额', text='地区', color='利润',
                             color_continuous_scale='RdYlGn')
            p = self._save_chart(fig, "region")
            if p: charts['region'] = p

        if '折扣率' in self.d.columns and self.d['折扣率'].nunique() > 1:
            disc = self.d[self.d['折扣率'] > 0].copy()
            if len(disc) > 10:
                fig = px.scatter(disc, x='折扣率', y='利润率', color='利润率', color_continuous_scale='RdYlGn',
                                 size='总销售额', size_max=15)
                p = self._save_chart(fig, "disc")
                if p: charts['disc'] = p

        # ★ 颜色偏好饼图 - 按颜色名称上色 ★
        if '颜色' in self.d.columns:
            cs = self.d.groupby('颜色', as_index=False)['总销售额'].sum()

            # 颜色名称 → hex 映射表
            color_map = {
                '黑': '#2C2C2C', '黑色': '#2C2C2C',
                '白': '#F5F5F5', '白色': '#F5F5F5', '米白': '#FFF8DC', '米色': '#F5F5DC',
                '红': '#E74C3C', '红色': '#E74C3C', '大红': '#DC143C', '酒红': '#800020', '暗红': '#8B0000',
                '粉': '#FFB6C1', '粉色': '#FFB6C1', '玫红': '#E30B5D',
                '橙': '#FF8C00', '橙色': '#FF8C00',
                '黄': '#F1C40F', '黄色': '#F1C40F', '米黄': '#F7DC6F',
                '绿': '#27AE60', '绿色': '#27AE60', '墨绿': '#1B4D3E', '军绿': '#4B5320', '草绿': '#7CFC00',
                '蓝': '#3498DB', '蓝色': '#3498DB', '深蓝': '#1B263B', '藏青': '#000080', '天蓝': '#87CEEB',
                '牛仔蓝': '#6F8FAF',
                '紫': '#9B59B6', '紫色': '#9B59B6', '薰衣草': '#E6E6FA',
                '灰': '#95A5A6', '灰色': '#95A5A6', '深灰': '#5D6D7E', '浅灰': '#D5D8DC',
                '棕': '#8B4513', '棕色': '#8B4513', '卡其': '#C3B091', '驼色': '#C19A6B', '咖啡': '#6F4E37',
                '金': '#FFD700', '金色': '#FFD700', '银': '#C0C0C0', '银色': '#C0C0C0',
                '花': '#DDA0DD', '碎花': '#DDA0DD', '条纹': '#4682B4', '格子': '#8B4513',
            }

            # 为每个颜色名匹配 hex，匹配不到就用调色板
            import plotly.express as px_colors
            palette = px_colors.colors.qualitative.Set3
            pie_colors = []
            for _, row in cs.iterrows():
                cname = str(row['颜色'])
                matched = False
                for key, hex_val in color_map.items():
                    if key in cname:
                        pie_colors.append(hex_val)
                        matched = True
                        break
                if not matched:
                    idx = len(pie_colors) % len(palette)
                    pie_colors.append(palette[idx])

            fig = px.pie(cs, values='总销售额', names='颜色', hole=0.4,
                         color='颜色',
                         color_discrete_map={row['颜色']: pie_colors[i] for i, (_, row) in enumerate(cs.iterrows())})

            # 白色/浅色需要深色边框才能看清
            fig.update_traces(
                marker=dict(line=dict(color='#FFFFFF', width=2)),
                textinfo='label+percent', textfont_size=12
            )
            p = self._save_chart(fig, "color")
            if p: charts['color'] = p

        return charts

    def _calc(self):
        total_sales = self.d['总销售额'].sum()
        total_profit = self.d['利润'].sum()
        profit_margin = total_profit / total_sales * 100 if total_sales > 0 else 0
        avg_order = self.d['总销售额'].mean() if len(self.d) > 0 else 0
        loss_items = self.d[self.d['利润率'] < 0]
        total_styles = self.d['子类别'].nunique() if '子类别' in self.d.columns else 1
        loss_styles = loss_items['子类别'].nunique() if '子类别' in loss_items.columns else 0
        return {
            'total_sales': total_sales, 'total_profit': total_profit,
            'profit_margin': profit_margin, 'avg_order': avg_order,
            'loss_count': len(loss_items), 'loss_styles': loss_styles,
            'total_styles': total_styles, 'records': len(self.d),
        }

    def _gen_suggestions(self):
        sugs = []
        if len(self.d) == 0:
            return ["当前筛选条件下无数据，请调整筛选条件"]

        kpi = self._calc()
        loss_ratio = kpi['loss_styles'] / kpi['total_styles'] * 100 if kpi['total_styles'] > 0 else 0
        if loss_ratio > 20:
            sugs.append(("严重亏损预警", f"当前 {kpi['loss_styles']} 个款（占比 {loss_ratio:.0f}%）处于亏损状态，建议立即全面审查定价与成本结构，停止亏损款补货并启动清仓。"))
        elif loss_ratio > 10:
            sugs.append(("中度亏损预警", f"{kpi['loss_styles']} 个款（占比 {loss_ratio:.0f}%）亏损，建议对亏损款进行提价测试或捆绑销售。"))
        elif loss_ratio > 0:
            sugs.append(("轻度亏损提示", f"仅 {kpi['loss_styles']} 个款亏损（占比 {loss_ratio:.0f}%），整体可控，建议针对性优化定价或进货成本。"))
        else:
            sugs.append(("经营状况良好", "当前无亏损款，所有品类均盈利，可继续当前策略并探索增长空间。"))

        if kpi['loss_styles'] > 0 and '子类别' in self.d.columns:
            loss = self.d[self.d['利润率'] < 0]
            loss_grp = loss.groupby('子类别', as_index=False)['利润'].sum().sort_values('利润')
            worst = loss_grp.iloc[0]['子类别']
            sugs.append(("重点亏损款", f"亏损最严重的款是【{worst}】（利润 {loss_grp.iloc[0]['利润']:,.0f} 元），建议优先处理：提价、减少进货或捆绑热销款清仓。"))

        if '月份' in self.d.columns and kpi['records'] > 0:
            last_months = sorted(self.d['月份'].unique())[-3:]
            recent = self.d[self.d['月份'].isin(last_months)]
            if len(recent) > 0:
                cat_share = recent.groupby('类别', as_index=False)['总销售额'].sum()
                cat_share['占比'] = cat_share['总销售额'] / cat_share['总销售额'].sum() * 100
                cat_share = cat_share.sort_values('占比', ascending=False)
                top3 = cat_share.head(3)
                sugs.append(("下月备货建议", "基于最近季度销售趋势，建议备货比例："))
                for _, row in top3.iterrows():
                    sugs.append(("", f"  · {row['类别']}：占比 {row['占比']:.1f}%，建议重点备货"))
                if '颜色' in recent.columns:
                    color_top = recent.groupby('颜色', as_index=False)['总销售额'].sum().sort_values('总销售额', ascending=False).iloc[0]
                    sugs.append(("", f"  颜色方面，【{color_top['颜色']}】近期热销，可多备该色系。"))

        cat = self.d.groupby('类别', as_index=False)['总销售额'].sum().sort_values('总销售额', ascending=False)
        if len(cat) > 0:
            top = cat.iloc[0]
            pct = top['总销售额'] / cat['总销售额'].sum() * 100
            sugs.append(("核心品类", f"{top['类别']} 是销售额主力（占总销售额 {pct:.1f}%），应作为重点运营品类，确保库存充足并加大营销投入。"))

        if '地区' in self.d.columns:
            rg = self.d.groupby('地区', as_index=False)['利润'].sum()
            best = rg.loc[rg['利润'].idxmax(), '地区']
            worst_r = rg.loc[rg['利润'].idxmin(), '地区']
            sugs.append(("地区策略", f"{best} 地区利润贡献最高，建议加大投放；{worst_r} 地区利润最低，需分析原因并调整策略。"))

        if '折扣率' in self.d.columns and self.d['折扣率'].nunique() > 1:
            dsc = self.d[(self.d['折扣率'] > 0) & (self.d['折扣率'] <= 100)]
            if len(dsc) > 10:
                bins = [0, 55, 65, 75, 85, 95, 101]
                labels = ['≤55折', '55-65折', '65-75折', '75-85折', '85-95折', '95-100折']
                dsc2 = dsc.copy()
                dsc2['_bin'] = pd.cut(dsc2['折扣率'], bins=bins, labels=labels, include_lowest=True)
                vp = dsc2.groupby('_bin', observed=True)['利润'].sum()
                if len(vp) > 1:
                    best_bin = vp.idxmax()
                    fp_profit = vp.get('95-100折', 0)
                    if vp[best_bin] > fp_profit:
                        sugs.append(("折扣策略", f"薄利多销分析显示，【{best_bin}】区间总利润最大，比正价多赚 ¥{vp[best_bin]-fp_profit:,.0f}。建议在此区间开展限时促销。"))
                    else:
                        sugs.append(("折扣策略", "当前数据表明正价销售利润最高，建议减少主动打折，清仓时再使用深度折扣。"))

        if '客户ID' in self.d.columns:
            cust = self.d.groupby('客户ID').agg(订单数=('总销售额', 'count'), 总消费=('总销售额', 'sum')).sort_values('总消费', ascending=False)
            total_cust = len(cust)
            vip = cust.head(5)
            vip_share = vip['总消费'].sum() / cust['总消费'].sum() * 100 if cust['总消费'].sum() > 0 else 0
            sugs.append(("客户价值", f"共 {total_cust} 位客户，Top5 客户贡献了 {vip_share:.1f}% 的销售额。建议建立 VIP 维护机制。"))
            repeat = (cust['订单数'] > 1).sum()
            repeat_rate = repeat / total_cust * 100 if total_cust > 0 else 0
            if repeat_rate < 20:
                sugs.append(("", f"客户复购率仅 {repeat_rate:.1f}%，建议推出会员卡或满减活动提升复购。"))

        return sugs

    def _find_chinese_font(self):
        """找中文字体，优先 .ttf"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base_dir, 'simhei.ttf'),
            os.path.join(base_dir, 'msyh.ttf'),
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\msyh.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def _wrap_text(self, c, text, max_width, font_name, font_size):
        """手动换行：把长文本按页面宽度切成多行"""
        c.setFont(font_name, font_size)
        lines = []
        # 按标点优先断句
        import re
        segments = re.split(r'([，。！？；、\n])', text)
        current_line = ""
        for seg in segments:
            if not seg:
                continue
            test_line = current_line + seg
            if c.stringWidth(test_line, font_name, font_size) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = seg
        if current_line:
            lines.append(current_line)
        return lines

    def generate(self, output_path: str = None) -> str:
        if output_path is None:
            output_path = os.path.join(self.tmpdir, "分析报告.pdf")

        charts = self._gen_charts()
        kpi = self._calc()
        sugs = self._gen_suggestions()

        # ===== 注册中文字体 =====
        font_path = self._find_chinese_font()
        if font_path:
            pdfmetrics.registerFont(TTFont('CN', font_path))
            font_name = 'CN'
        else:
            # 没有中文字体就用内置 Helvetica（中文会显示为方块，但至少不报错）
            font_name = 'Helvetica'

        # ===== 创建 PDF =====
        c = canvas.Canvas(output_path, pagesize=A4)
        page_w, page_h = A4
        margin = 20 * mm
        content_w = page_w - 2 * margin
        y = page_h - margin

        # ===== 封面 =====
        # 标题
        c.setFont(font_name, 28)
        c.setFillColor(HexColor("#1a1a2e"))
        title = "服装销售数据分析报告"
        title_w = c.stringWidth(title, font_name, 28)
        c.drawString((page_w - title_w) / 2, y - 40, title)

        # 分隔线
        y -= 70
        c.setStrokeColor(HexColor("#FF4B4B"))
        c.setLineWidth(2)
        c.line(margin, y, page_w - margin, y)

        # 信息
        y -= 30
        c.setFont(font_name, 14)
        c.setFillColor(HexColor("#333333"))
        info_lines = [
            f"数据范围：{self.category} / {self.region}",
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"有效记录数：{kpi['records']} 条",
        ]
        for line in info_lines:
            c.drawCentredString(page_w / 2, y, line)
            y -= 22

        # ===== 核心指标 =====
        c.showPage()
        y = page_h - margin

        c.setFont(font_name, 18)
        c.setFillColor(HexColor("#1a1a2e"))
        c.drawString(margin, y, "一、核心指标")
        y -= 35

        # 指标卡片背景
        metrics = [
            ("总销售额", f"{kpi['total_sales']:,.0f} 元"),
            ("总利润", f"{kpi['total_profit']:,.0f} 元"),
            ("客单价", f"{kpi['avg_order']:,.0f} 元"),
            ("整体利润率", f"{kpi['profit_margin']:.1f}%"),
        ]
        if kpi['loss_count'] > 0:
            metrics.append(("亏损记录数", f"{kpi['loss_count']} 条（涉及 {kpi['loss_styles']} 个款）"))

        card_h = 28
        for label, value in metrics:
            # 标签
            c.setFont(font_name, 11)
            c.setFillColor(HexColor("#666666"))
            c.drawString(margin + 5, y, label)
            # 值
            c.setFont(font_name, 13)
            c.setFillColor(HexColor("#FF4B4B") if "亏损" in label else HexColor("#1a1a2e"))
            c.drawString(margin + 120, y, value)
            y -= card_h

        y -= 15

        # ===== 图表区 =====
        c.setFont(font_name, 18)
        c.setFillColor(HexColor("#1a1a2e"))
        c.drawString(margin, y, "二、数据可视化分析")
        y -= 30

        chart_titles = {
            'cat': '各类别销售额对比', 'mon': '月度销售趋势',
            'profit': '子类别利润排行', 'region': '各地区销售表现',
            'disc': '折扣率与利润率关系', 'color': '颜色偏好分布',
        }

        for key, path in charts.items():
            if not os.path.exists(path):
                continue
            # 新页
            c.showPage()
            y = page_h - margin

            # 标题
            c.setFont(font_name, 14)
            c.setFillColor(HexColor("#1a1a2e"))
            c.drawString(margin, y, chart_titles.get(key, ''))
            y -= 20

            # 图片
            img = ImageReader(path)
            img_w = content_w
            img_h = 200 * mm
            c.drawImage(img, margin, y - img_h, width=img_w, height=img_h, preserveAspectRatio=True)

        # ===== 经营建议 =====
        c.showPage()
        y = page_h - margin

        c.setFont(font_name, 18)
        c.setFillColor(HexColor("#1a1a2e"))
        c.drawString(margin, y, "三、智能经营建议")
        y -= 30

        line_height = 18
        for title, content in sugs:
            # 检查是否需要新页
            text_lines = self._wrap_text(c, content, content_w - 10, font_name, 11)
            needed_h = line_height * (len(text_lines) + 1) + 10
            if y - needed_h < margin + 20:
                c.showPage()
                y = page_h - margin

            if title:
                c.setFont(font_name, 12)
                c.setFillColor(HexColor("#FF4B4B"))
                c.drawString(margin, y, f"【{title}】")
                y -= line_height + 4

            if content:
                c.setFont(font_name, 11)
                c.setFillColor(HexColor("#333333"))
                for line in text_lines:
                    if y < margin + 10:
                        c.showPage()
                        y = page_h - margin
                    c.drawString(margin + 5, y, line)
                    y -= line_height
                y -= 5

        # ===== 页脚 =====
        c.setFont(font_name, 9)
        c.setFillColor(HexColor("#999999"))
        footer = "本报告由数据分析看板自动生成，数据仅供参考，不构成投资决策依据。"
        c.drawCentredString(page_w / 2, 15 * mm, footer)
        c.drawCentredString(page_w / 2, 10 * mm, f"生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        c.save()
        self._cleanup()
        return output_path