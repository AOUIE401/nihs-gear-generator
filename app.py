import streamlit as st
import math
import ezdxf
import io
import matplotlib.pyplot as plt

# --- 1. 計算ロジック ---
def get_f(z):
    if z <= 8: return 2.32
    elif z == 9: return 2.34
    elif z <= 11: return 2.38
    elif z <= 13: return 2.40
    elif z <= 16: return 2.44
    elif z <= 20: return 2.48
    elif z <= 25: return 2.52
    elif z <= 34: return 2.54
    elif z <= 54: return 2.58
    elif z <= 134: return 2.62
    else: return 2.64

def generate_gear_data(m, z, res=30):
    f = get_f(z)
    da = m * (z + f)
    df = m * (z - 3.5)
    s = 1.41 * m
    rho = 0.8 * f * m
    Ra = da / 2
    Rf = df / 2

    Xc = s / 2 - rho
    Yc = Ra - math.sqrt(rho**2 - Xc**2)

    L = math.sqrt(Xc**2 + Yc**2)
    phi = math.atan2(Yc, Xc)
    theta = math.asin(rho / L)
    alpha = phi - theta
    OT = math.sqrt(L**2 - rho**2)
    
    T1x = OT * math.cos(alpha)
    T1y = OT * math.sin(alpha)

    gamma = alpha
    theta_z = 2 * math.pi / z
    theta_mid = math.pi / 2 - theta_z / 2
    psi = gamma - theta_mid

    rc = Rf * math.sin(psi) / (1 - math.sin(psi))
    D = Rf + rc
    Ckx = D * math.cos(theta_mid)
    Cky = D * math.sin(theta_mid)

    Lt = D * math.cos(psi)
    T2x = Lt * math.cos(gamma) 
    T2y = Lt * math.sin(gamma)
    
    T3_ang = theta_mid - psi
    T3x = Lt * math.cos(T3_ang) 
    T3y = Lt * math.sin(T3_ang)

    # DXF用 Bulge (ふくらみ) の計算
    a1_L = math.atan2(T1y - Yc, -T1x - (-Xc))
    a2_L = math.atan2(Ra - Yc, 0 - (-Xc))
    d_L = a2_L - a1_L
    if d_L > 0: d_L -= 2 * math.pi
    bulge_L = math.tan(d_L / 4)

    a1_R = math.atan2(Ra - Yc, 0 - Xc)
    a2_R = math.atan2(T1y - Yc, T1x - Xc)
    d_R = a2_R - a1_R
    if d_R > 0: d_R -= 2 * math.pi
    bulge_R = math.tan(d_R / 4)

    a1_Kc = math.atan2(T2y - Cky, T2x - Ckx)
    a2_Kc = math.atan2(T3y - Cky, T3x - Ckx)
    d_Kc = a2_Kc - a1_Kc
    if d_Kc < 0: d_Kc += 2 * math.pi
    bulge_Kc = math.tan(d_Kc / 4)

    dxf_pts = []
    for i in range(z):
        rot = -i * theta_z
        cos_r = math.cos(rot)
        sin_r = math.sin(rot)
        def r_pt(x, y): return (x * cos_r - y * sin_r, x * sin_r + y * cos_r)

        px, py = r_pt(-T2x, T2y)
        dxf_pts.append((px, py, 0))        
        
        px, py = r_pt(-T1x, T1y)
        dxf_pts.append((px, py, bulge_L))  
        
        px, py = r_pt(0, Ra)
        dxf_pts.append((px, py, bulge_R))  
        
        px, py = r_pt(T1x, T1y)
        dxf_pts.append((px, py, 0))        
        
        px, py = r_pt(T2x, T2y)
        dxf_pts.append((px, py, bulge_Kc)) 

    # プレビュー表示用のポリゴン座標
    ang_top = math.atan2(Ra - Yc, 0 - Xc)
    ang_T1 = math.atan2(T1y - Yc, T1x - Xc)
    if ang_T1 > ang_top: ang_T1 -= 2 * math.pi
    pts_add_R = []
    for i in range(res + 1):
        a = ang_top + (ang_T1 - ang_top) * (i / res)
        pts_add_R.append((Xc + rho * math.cos(a), Yc + math.sin(a) * rho))
    pts_add_L = [(-x, y) for x, y in reversed(pts_add_R)]

    ang_T2 = math.atan2(T2y - Cky, T2x - Ckx)
    ang_T3 = math.atan2(T3y - Cky, T3x - Ckx)
    if ang_T3 < ang_T2: ang_T3 += 2 * math.pi
    pts_fillet = []
    for i in range(res + 1):
        a = ang_T2 + (ang_T3 - ang_T2) * (i / res)
        pts_fillet.append((Ckx + rc * math.cos(a), Cky + rc * math.sin(a)))

    pitch_pts = [(-T2x, T2y)] + pts_add_L + pts_add_R[1:] + [(T2x, T2y)] + pts_fillet[1:]
    
    preview_pts = []
    for i in range(z):
        rot = -i * theta_z
        cos_r = math.cos(rot)
        sin_r = math.sin(rot)
        for px, py in pitch_pts[:-1]: 
            preview_pts.append((px * cos_r - py * sin_r, px * sin_r + py * cos_r))
    preview_pts.append(preview_pts[0]) 

    return dxf_pts, preview_pts

# --- 2. Streamlit UI ---
st.set_page_config(page_title="NIHS Gear ジェネレータ", layout="centered", page_icon="⚙️")

lang = st.radio("Language / 言語", ["日本語", "English"], horizontal=True)
def t(ja, en): return ja if lang == "日本語" else en

st.title(t("⌚ NIHS 20-25 歯車ジェネレータ", "⌚ NIHS 20-25 Gear Generator"))
st.caption("Created by AOUIE K") # 🌟 ここに追加しました！

col1, col2 = st.columns(2)
with col1:
    m_val = st.number_input(t("モジュール (m) [単位: mm]", "Module (m) [Unit: mm]"), 0.01, 10.0, 0.20, 0.01)
with col2:
    z_val = st.number_input(t("歯数 (z)", "Teeth (z)"), 6, 400, 30)

dxf_pts, preview_pts = generate_gear_data(m_val, z_val)

fig, ax = plt.subplots(figsize=(6, 6))
px, py = zip(*preview_pts)
ax.plot(px, py, color='#1E88E5', lw=1.0)
ax.fill(px, py, color='#1E88E5', alpha=0.1) 
ax.set_aspect('equal')
ax.axis('off')
plt.tight_layout()
st.pyplot(fig)

# DXFエクスポート (単位: mm 固定)
doc = ezdxf.new('R2010')
doc.header['$MEASUREMENT'] = 1  
doc.header['$INSUNITS'] = 4     
doc.units = ezdxf.units.MM

msp = doc.modelspace()
msp.add_lwpolyline(dxf_pts, format='xyb', dxfattribs={'closed': True})
out = io.StringIO()
doc.write(out)

st.download_button(
    label=t("💾 DXFをダウンロード", "💾 Download DXF"),
    data=out.getvalue(),
    file_name=f"NIHS_Gear_m{m_val}_z{z_val}.dxf",
    mime="application/dxf",
    use_container_width=True
)