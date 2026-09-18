import sys
import os
import io
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from analysis_engine import FashionAnalyzer

st.set_page_config(page_title="服装销售数据分析看板", page_icon="👗", layout="wide")

# ==================== 智能读取 CSV ====================
def smart_read_csv(raw_bytes):
    """智能读取 CSV：自动识别编码、分隔符"""
    encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']
    for enc in encodings:
        try:
            text = raw_bytes.decode(enc)
            sep = '\t' if text.count('\t') > text.count(',') else ','
            return pd.read_csv(io.StringIO(text), sep=sep)
        except Exception:
            continue
    return pd.read_csv(io.BytesIO(raw_bytes))

# ==================== 数据加载 ====================
@st.cache_data(show_spinner="正在加载数据...")
def load_dataframe():
    """加载数据：优先用 FashionAnalyzer，否则直接读 CSV"""
    try:
        analyzer = FashionAnalyzer()
        return analyzer.df, False
    except Exception:
        for fname in ['fashion_sales_data.csv', 'fashion_sales_realistic.csv']:
            if os.path.exists(fname):
                return smart_read_csv(open(fname, 'rb').read()), False
        return pd.DataFrame(), False

_default_df, _ = load_dataframe()

# ==================== 顶部：CSV 上传 ====================
st.title("👗 服装销售数据分析看板")

st.markdown("### 📤 上传你的销售数据（可选）")
st.caption("支持 Excel 导出的 CSV 文件，上传后看板将自动刷新。不传则使用示例数据演示。")

uploaded_file = st.file_uploader(
    "选择 CSV 文件",
    type=["csv"],
    help="至少包含「总销售额」列；有「利润」「订单日期」列分析更准"
)

COLUMN_MAP = {
    '订单日期': ['订单日期','日期','销售日期','下单日期','order_date','date','交易日'],
    '类别':     ['类别','产品类别','商品类别','大类','category','产品类型','type'],
    '子类别':   ['子类别','子类','产品','商品','商品名称','款式','子品类','product','item'],
    '总销售额': ['总销售额','销售额','销售金额','金额','成交金额','收入','sales','revenue','amount','总价'],
    '利润':     ['利润','毛利','盈利','profit','margin'],
    '数量':     ['数量','销量','件数','销售数量','qty','quantity','件'],
    '地区':     ['地区','区域','城市','省份','region','area','city'],
    '颜色':     ['颜色','colour','color'],
    '尺码':     ['尺码','size'],
    '折扣率':   ['折扣率','折扣','discount','折'],
}

df = _default_df.copy()
is_uploaded = False

if uploaded_file is not None:
    try:
        raw = uploaded_file.getvalue()
        df_upload = smart_read_csv(raw)

        # ---- 字段名映射 ----
        col_lower = {c: c.lower().strip() for c in df_upload.columns}
        rename_map = {}
        for std_name, aliases in COLUMN_MAP.items():
            for alias in aliases:
                matches = [c for c, cl in col_lower.items() if cl == alias.lower().strip()]
                if matches:
                    rename_map[matches[0]] = std_name
                    break
        df_upload = df_upload.rename(columns=rename_map)

        # ---- 必要字段检查 ----
        if '总销售额' not in df_upload.columns:
            st.error(f"❌ 上传的文件缺少必要列 `总销售额`。当前列：{list(df_upload.columns)}")
            st.info("💡 支持的列名：销售额 / 销售金额 / 金额 / 收入 / 总销售额 等，系统自动识别")
        else:
            # ---- 智能补全 ----
            if '利润' not in df_upload.columns:
                df_upload['利润'] = df_upload['总销售额'] * 0.25
                st.warning("ℹ️ 未检测到「利润」列，已按销售额 25% 估算（演示用），实际请补充利润列")
            if '数量' not in df_upload.columns:
                df_upload['数量'] = 1
            if '类别' not in df_upload.columns:
                df_upload['类别'] = '未分类'
            if '子类别' not in df_upload.columns:
                for c in ['产品', '商品', '商品名称']:
                    if c in df_upload.columns:
                        df_upload['子类别'] = df_upload[c]
                        break
                else:
                    df_upload['子类别'] = '未知'

            # ★ 修复：用 .where() 替代 np.where()，返回 Series 才有 .fillna()
            if '折扣率' in df_upload.columns:
                d = pd.to_numeric(df_upload['折扣率'], errors='coerce')
                df_upload['折扣率'] = d.where(d > 10, d * 100).fillna(100)
            else:
                df_upload['折扣率'] = 100

            for col in ['总销售额', '利润', '数量']:
                df_upload[col] = pd.to_numeric(df_upload[col], errors='coerce').fillna(0)

            if '利润率' not in df_upload.columns:
                df_upload['利润率'] = np.where(
                    df_upload['总销售额'] > 0,
                    df_upload['利润'] / df_upload['总销售额'] * 100, 0
                )
            else:
                df_upload['利润率'] = pd.to_numeric(df_upload['利润率'], errors='coerce').fillna(0)

            # ---- 月份提取 ----
            if '月份' not in df_upload.columns and '订单日期' in df_upload.columns:
                dt = pd.to_datetime(df_upload['订单日期'], errors='coerce')
                df_upload['月份'] = dt.dt.month.fillna(1)
            elif '月份' not in df_upload.columns:
                df_upload['月份'] = 1

            st.success(f"✅ 成功加载 **{len(df_upload)}** 条记录，已自动识别列名")
            with st.expander("🔍 查看识别到的字段映射"):
                st.write({v: k for k, v in rename_map.items()})
            df = df_upload
            is_uploaded = True

    except Exception as e:
        st.error(f"❌ 文件读取失败：{e}")
        st.info("💡 请确认是标准 CSV，可用 Excel「另存为 → CSV (逗号分隔)」重新导出")
else:
    st.info("ℹ️ 当前显示的是**示例数据**。上传你的真实数据后，所有图表自动刷新。")

st.markdown("---")

# ==================== 折扣率归一化（主逻辑） ====================
# ★ 修复：同样用 .where() 替代 np.where()
if '折扣率' in df.columns:
    d = pd.to_numeric(df['折扣率'], errors='coerce')
    df['折扣率'] = d.where(d > 10, d * 100).fillna(100)
else:
    df['折扣率'] = 100

HAS_DISCOUNT = df['折扣率'].notna().sum() > 0 and df['折扣率'].nunique() > 1

if '利润率' not in df.columns:
    df['利润率'] = np.where(df['总销售额'] > 0, df['利润'] / df['总销售额'] * 100, 0)
if '月份' not in df.columns:
    df['月份'] = 1

# ==================== 侧边栏筛选 ====================
with st.sidebar:
    st.header("🔍 筛选条件")
    st.success("📄 使用上传数据" if is_uploaded else "📊 使用示例数据")
    categories = ['全部'] + sorted(df['类别'].dropna().unique().tolist())
    regions = ['全部'] + sorted(df['地区'].dropna().unique().tolist()) if '地区' in df.columns else ['全部']
    selected_category = st.selectbox("选择品类", categories)
    selected_region = st.selectbox("选择地区", regions)
    st.markdown("---")
    st.caption("筛选后所有图表实时联动")

df_filtered = df.copy()
if selected_category != '全部':
    df_filtered = df_filtered[df_filtered['类别'] == selected_category]
if selected_region != '全部' and '地区' in df.columns:
    df_filtered = df_filtered[df_filtered['地区'] == selected_region]

no_data = len(df_filtered) == 0

# ==================== 第一行：KPI ====================
st.subheader("📊 核心指标")
k1, k2, k3, k4 = st.columns(4)
total_sales = df_filtered['总销售额'].sum()
total_profit = df_filtered['利润'].sum()
avg_order = df_filtered['总销售额'].mean() if not no_data else 0
profit_margin = total_profit / total_sales * 100 if total_sales > 0 else 0
k1.metric("总销售额", f"¥{total_sales:,.0f}")
k2.metric("总利润", f"¥{total_profit:,.0f}")
k3.metric("客单价", f"¥{avg_order:,.0f}")
k4.metric("整体利润率", f"{profit_margin:.1f}%")
st.markdown("---")

# ==================== 第二行：类别 + 月度 ====================
c1, c2 = st.columns(2)
with c1:
    st.subheader("📦 各类别销售额对比")
    if not no_data:
        cat = df_filtered.groupby('类别', as_index=False)['总销售额'].sum().sort_values('总销售额', ascending=False)
        fig = px.bar(cat, x='类别', y='总销售额', color='总销售额', color_continuous_scale='Blues', text='总销售额')
        fig.update_traces(texttemplate='¥%{text:,.0f}', textposition='outside')
        fig.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.info(f"💡 **{cat.iloc[0]['类别']}** 销售额最高，占 {cat.iloc[0]['总销售额']/cat['总销售额'].sum()*100:.1f}%")
    else:
        st.warning("无数据")

with c2:
    st.subheader("📅 月度销售趋势")
    if not no_data:
        mon = df_filtered.groupby('月份', as_index=False)['总销售额'].sum().sort_values('月份')
        fig = px.line(mon, x='月份', y='总销售额', markers=True, line_shape='spline', text='总销售额')
        fig.update_traces(line=dict(width=3, color='#FF4B4B'), marker=dict(size=8),
                          texttemplate='¥%{text:,.0f}', textposition='top center')
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        pk = int(mon.loc[mon['总销售额'].idxmax(), '月份'])
        st.info(f"💡 第 **{pk}** 月是销售高峰，建议提前2周备货")
    else:
        st.warning("无数据")
st.markdown("---")

# ==================== 第三行：利润排行 + 地区 ====================
c3, c4 = st.columns(2)
with c3:
    st.subheader("💰 子类别利润排行（TOP 10）")
    if not no_data:
        pr = df_filtered.groupby('子类别', as_index=False)['利润'].sum().sort_values('利润', ascending=False).head(10)
        colors_bar = ['#FF4B4B' if v < 0 else '#00CC96' for v in pr['利润']]
        fig = go.Figure(go.Bar(x=pr['利润'], y=pr['子类别'], orientation='h', marker_color=colors_bar,
                               text=[f'¥{v:,.0f}' for v in pr['利润']], textposition='outside'))
        fig.update_layout(yaxis=dict(autorange='reversed'), height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        loss = pr[pr['利润'] < 0]
        if len(loss) > 0:
            st.error(f"⚠️ **亏损预警**：{', '.join(loss['子类别'])} 利润为负，建议提价或停止补货")
        else:
            st.success("✅ 所有子类别均盈利")
    else:
        st.warning("无数据")

with c4:
    st.subheader("🗺️ 各地区销售表现")
    if not no_data and '地区' in df.columns:
        rg = df_filtered.groupby('地区', as_index=False).agg(总销售额=('总销售额', 'sum'), 利润=('利润', 'sum'))
        fig = px.scatter(rg, x='总销售额', y='利润', size='总销售额', text='地区', color='利润', color_continuous_scale='RdYlGn', size_max=60)
        fig.update_traces(textposition='middle center', textfont=dict(size=14, color='white'))
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.info(f"💡 **{rg.loc[rg['利润'].idxmax(), '地区']}** 利润最高，可加大投放")
    else:
        st.warning("无「地区」列数据")
st.markdown("---")

# ==================== 第四行：颜色 + 尺码 ====================
c5, c6 = st.columns(2)
with c5:
    st.subheader("🎨 颜色偏好分析")
    if not no_data and '颜色' in df.columns:
        cs = df_filtered.groupby('颜色', as_index=False)['总销售额'].sum().sort_values('总销售额', ascending=False)
        fig = px.pie(cs, values='总销售额', names='颜色', hole=0.4)
        fig.update_traces(textinfo='label+percent', textfont_size=12)
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.info(f"💡 **{cs.iloc[0]['颜色']}** 最受欢迎，进货可优先")
    else:
        st.warning("无「颜色」列数据")

with c6:
    st.subheader("📏 尺码销量分布")
    if not no_data and '尺码' in df.columns:
        sz = df_filtered.groupby('尺码', as_index=False)['数量'].sum()
        fig = px.bar(sz, x='尺码', y='数量', color='数量', color_continuous_scale='Viridis', text='数量')
        fig.update_traces(texttemplate='%{text} 件', textposition='outside')
        fig.update_layout(height=400, showlegend=False, xaxis=dict(categoryorder='total descending'))
        st.plotly_chart(fig, use_container_width=True)
        st.info(f"💡 **{sz.loc[sz['数量'].idxmax(), '尺码']}** 码销量最大，库存向该尺码倾斜")
    else:
        st.warning("无「尺码」列数据")
st.markdown("---")

# ==================== 第五行：折扣分析 ====================
st.subheader("💸 折扣力度对利润的影响")

if not HAS_DISCOUNT:
    st.info("ℹ️ 数据中折扣值单一或无折扣字段，跳过折扣分析")
else:
    dsc = df_filtered.copy()
    dsc = dsc[(dsc['折扣率'] > 0) & (dsc['折扣率'] <= 100)]

    # ---- 第一层：整体趋势 ----
    st.markdown("##### 📉 整体趋势")
    if len(dsc) < 3:
        st.warning(f"⚠️ 当前筛选范围内仅 {len(dsc)} 条折扣记录，样本太少")
    else:
        corr = dsc['折扣率'].corr(dsc['利润率'])
        x, y = dsc['折扣率'], dsc['利润率']
        denom = len(x) * (x**2).sum() - (x.sum())**2
        slope = (len(x) * (x*y).sum() - x.sum()*y.sum()) / denom if denom != 0 else 0

        c7, c8, c9 = st.columns(3)
        c7.metric("折扣-利润率相关系数", f"{corr:.3f}")
        c8.metric("趋势斜率", f"{slope:.2f}")
        c9.metric("有效样本数", f"{len(dsc)}")
        st.info(f"💡 折扣率每降低10%（多打1折），利润率平均{'下降' if slope < 0 else '上升'} {abs(slope*0.1):.1f}%")

        try:
            dsc['_bin'] = pd.cut(dsc['折扣率'], bins=min(10, len(dsc)//2+1), include_lowest=True)
            bin_df = dsc.groupby('_bin', observed=True).agg(平均利润率=('利润率', 'mean'), 订单数=('利润率', 'count')).reset_index()
            bin_df['_bin'] = bin_df['_bin'].astype(str)
            if len(bin_df) > 1:
                fig = px.bar(bin_df, x='_bin', y='平均利润率', color='平均利润率', color_continuous_scale='RdYlGn', text='平均利润率')
                fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass

    st.markdown("---")

    # ---- 第二层：盈亏线 ----
    st.markdown("##### 🎯 盈亏平衡 / 利润预警线")
    HEALTHY_MARGIN = 10

    can_group = ('子类别' in dsc.columns and
                 dsc['子类别'].nunique() > 1 and
                 len(dsc) >= 4)

    if can_group:
        items = []
        for sub, g in dsc.groupby('子类别'):
            if len(g) < 2:
                continue
            grp = g.groupby('折扣率')['利润率'].mean().reset_index().sort_values('折扣率')
            warning_grp = grp[grp['利润率'] < HEALTHY_MARGIN]
            if len(warning_grp) > 0:
                be = float(warning_grp['折扣率'].max())
                status = "⚠️ 利润预警"
            else:
                be = float(grp.loc[grp['利润率'].idxmin(), '折扣率'])
                status = "✅ 健康"

            fp = g[g['折扣率'] >= 95]
            fm = float(fp['利润率'].mean()) if len(fp) > 0 else float(g['利润率'].mean())
            items.append({
                "sub_category": str(sub), "break_even": be,
                "status": status, "min_margin": round(float(grp['利润率'].min()), 1),
                "full_margin": round(fm, 1), "count": len(g)
            })

        if items:
            be_df = pd.DataFrame(items).sort_values('break_even', ascending=True)

            be_show = be_df.rename(columns={
                'sub_category': '子类别', 'status': '状态',
                'break_even': '预警/盈亏线', 'min_margin': '最低利润率',
                'full_margin': '正价利润率', 'count': '样本数'
            })[['子类别', '预警/盈亏线', '状态', '最低利润率', '正价利润率', '样本数']].copy()
            be_show['预警/盈亏线'] = be_show['预警/盈亏线'].apply(lambda v: f"{v:.0f}%（打{v/10:.1f}折）")
            be_show['最低利润率'] = be_show['最低利润率'].apply(lambda v: f"{v:.1f}%")
            be_show['正价利润率'] = be_show['正价利润率'].apply(lambda v: f"{v:.1f}%")
            st.dataframe(be_show, use_container_width=True, hide_index=True)

            fig = px.bar(be_df, x='sub_category', y='break_even', color='break_even',
                         color_continuous_scale='RdYlGn_r', text='break_even',
                         labels={'sub_category': '子类别', 'break_even': '盈亏平衡折扣率 (%)'})
            fig.update_traces(texttemplate='%{text:.0f}%', textposition='outside')
            fig.add_hline(y=80, line_dash='dot', line_color='gray', annotation_text='8折参考线')
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            worst = be_df.iloc[-1]
            st.warning(f"⚠️ **{worst['sub_category']}** 盈亏/预警线最高（{worst['break_even']:.0f}%），最怕打折，建议正价销售或仅参与满减")
            st.caption(f"📌 预警线定义：利润率低于 {HEALTHY_MARGIN}% 即触发预警")
        else:
            st.info("样本不足，无法计算盈亏线")
    else:
        st.info("📊 当前数据量较少，采用「整体模式」展示盈亏线")
        grp = dsc.groupby('折扣率')['利润率'].mean().reset_index().sort_values('折扣率')
        if len(grp) > 1:
            fig = px.line(grp, x='折扣率', y='利润率', markers=True, line_shape='spline')
            fig.add_hline(y=0, line_dash='dash', line_color='red', annotation_text='盈亏线')
            fig.add_hline(y=HEALTHY_MARGIN, line_dash='dot', line_color='orange', annotation_text=f'{HEALTHY_MARGIN}%预警线')
            fig.update_layout(xaxis_title='折扣率 (%)', yaxis_title='利润率 (%)', height=400)
            st.plotly_chart(fig, use_container_width=True)

            warning = grp[grp['利润率'] < HEALTHY_MARGIN]
            if len(warning) > 0:
                be = float(warning['折扣率'].max())
                st.success(f"✅ 整体利润预警线约 **{be:.0f}%（打{be/10:.1f}折）**——折扣高于此值健康，低于此值利润偏薄")
            else:
                st.info("当前折扣范围内利润率均高于预警线")

    st.markdown("---")

    # ---- 第三层：薄利多销 ----
    st.markdown("##### 🎰 薄利多销最优折扣区间")
    bins = [0, 55, 65, 75, 85, 95, 101]
    labels = ['≤55折', '55-65折', '65-75折', '75-85折', '85-95折', '95-100折']
    dsc['_bin'] = pd.cut(dsc['折扣率'], bins=bins, labels=labels, include_lowest=True)
    vp = dsc.groupby('_bin', observed=True).agg(总销量=('数量', 'sum'), 总利润=('利润', 'sum')).reset_index().dropna()

    if len(vp) > 1:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=vp['_bin'].astype(str), y=vp['总销量'], name='总销量', marker_color='lightblue', opacity=0.7, yaxis='y1'))
        fig.add_trace(go.Scatter(x=vp['_bin'].astype(str), y=vp['总利润'], mode='lines+markers+text', name='总利润',
                                 line=dict(color='#FF4B4B', width=3), marker=dict(size=9),
                                 text=[f'¥{v/1000:.1f}千' if abs(v) > 0 else '' for v in vp['总利润']],
                                 textposition='top center', yaxis='y2'))
        fig.update_layout(xaxis_title='折扣区间', yaxis=dict(title='总销量'),
                          yaxis2=dict(title='总利润', overlaying='y', side='right', showgrid=False),
                          height=420, legend=dict(orientation='h', yanchor='bottom', y=1.02))
        st.plotly_chart(fig, use_container_width=True)

        best = vp.loc[vp['总利润'].idxmax()]
        fp = vp[vp['_bin'] == '95-100折']
        fp_profit = float(fp['总利润'].values[0]) if len(fp) > 0 else 0
        fp_vol = float(fp['总销量'].values[0]) if len(fp) > 0 else 0
        diff = float(best['总利润'] - fp_profit)
        vol_lift = (best['总销量'] - fp_vol) / fp_vol * 100 if fp_vol > 0 else 0

        c10, c11 = st.columns(2)
        c10.metric("最优折扣区间", str(best['_bin']))
        c11.metric("该区间总利润", f"¥{float(best['总利润']):,.0f}")
        c12, c13 = st.columns(2)
        c12.metric("比正价多赚", f"¥{diff:,.0f}")
        c13.metric("销量提升", f"{vol_lift:.1f}%")

        if diff > 0:
            st.success(f"✅ **建议**：最优促销折扣 **{best['_bin']}**，比正价多赚 ¥{diff:,.0f}，可在此区间做限时促销")
        else:
            st.info(f"ℹ️ 当前数据表明正价销售利润最高，不建议主动打折；如需清仓可放宽至 {best['_bin']}")
    else:
        st.info("折扣区间数据不足，无法判断最优折扣")

st.markdown("---")

# ==================== 第六行：亏损款明细 ====================
st.subheader("🚨 亏损款明细（利润率 < 0）")
if not no_data:
    loss = df_filtered[df_filtered['利润率'] < 0]
    if len(loss) > 0:
        grp_cols = [c for c in ['子类别', '颜色', '尺码'] if c in loss.columns]
        if not grp_cols:
            grp_cols = ['子类别']
        ls = loss.groupby(grp_cols).agg(销售额=('总销售额', 'sum'), 利润=('利润', 'sum'), 销量=('数量', 'sum')).reset_index()
        ls['利润率'] = (ls['利润'] / ls['销售额'].replace(0, np.nan) * 100).round(1)
        ls = ls.sort_values('利润')
        st.dataframe(ls.style.format({'销售额': '¥{:,.0f}', '利润': '¥{:,.0f}', '利润率': '{:.1f}%', '销量': '{:,} 件'}).background_gradient(subset=['利润率'], cmap='Reds'), use_container_width=True)
        st.error(f"⚠️ 共 **{len(ls)}** 个亏损组合：建议提价 / 停止补货 / 捆绑清仓")
    else:
        st.success("✅ 当前无亏损款，经营状况良好！")
else:
    st.warning("无数据")

# ==================== 原始数据 ====================
with st.expander("📋 查看原始数据"):
    st.dataframe(df_filtered, use_container_width=True)
    csv_out = df_filtered.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("📥 下载当前数据 CSV", csv_out, "筛选结果.csv", "text/csv")

st.caption(f"📊 分析引擎：FashionAnalyzer · 数据来源：{'客户上传' if is_uploaded else '示例数据'} · {pd.Timestamp.now():%Y-%m-%d %H:%M}")


from report_generator import ReportGenerator
from datetime import datetime

st.markdown("---")
st.subheader("📄 生成分析报告")
col_btn1, col_btn2 = st.columns([1, 2])
with col_btn1:
    generate_btn = st.button("📥 生成 PDF 分析报告", type="primary", use_container_width=True)
with col_btn2:
    st.caption("根据当前筛选条件，生成一份包含核心指标、可视化图表和经营建议的 PDF 报告")

if generate_btn:
    with st.spinner("正在生成报告，请稍候..."):
        try:
            rg = ReportGenerator(
                df=df, df_filtered=df_filtered,
                category=selected_category, region=selected_region
            )
            pdf_path = rg.generate()
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            st.success("✅ 报告生成成功！")
            st.download_button(
                label="📥 下载 PDF 报告",
                data=pdf_bytes,
                file_name=f"销售分析报告_{selected_category}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"❌ 报告生成失败：{e}")