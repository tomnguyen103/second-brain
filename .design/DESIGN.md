# DESIGN.md - WattVision Electrical Monitoring System

## 1. Visual Theme & Atmosphere
The design must communicate **technical reliability** and **control**. It should not feel like a social network or a game app. The interface is intended for laptop or tablet use in a home or small business setting in Bolivia. The atmosphere is a simplified "Power BI Dashboard" for an end user.

## 2. Color Palette
- **Primary background:** `#121212` (dark mode for visual efficiency and data emphasis).
- **Card surface:** `#1E1E1E`.
- **Primary accent (data):** `#00E5FF` (cyan/neon) for charts, primary KPIs, and action buttons.
- **Alert accent:** `#FF453A` (red) for consumption spikes or vampire-load alerts.
- **Secondary accent:** `#32D74B` (lime green) for "Live" status and normal values.
- **Primary text:** `#FFFFFF` (high contrast).
- **Secondary text:** `#98989D` (gray for labels).

### Warm Light Inspection Theme
Second Brain keeps WattVision as a dark-first system, but also supports an explicitly approved low-glare light inspection mode. Use this only for the `.light` theme variant, not as the primary product tone.

- **Background:** `#E9E1D5`.
- **Foreground:** `#211C18`.
- **Card surface:** `#F4EEE4`.
- **Popover surface:** `#F7F1E8`.
- **Primary accent:** `#007C89`.
- **Primary foreground:** `#FFF8EF`.
- **Secondary surface:** `#DED4C7`.
- **Muted surface:** `#DDD3C5`.
- **Muted text:** `#6F6459`.
- **Accent surface:** `#D7E8E3`.
- **Accent foreground:** `#1D3838`.
- **Alert accent:** `#B42318`.
- **Border:** `#CDBFAC`.
- **Input border:** `#C8B9A6`.
- **Live accent:** `#1F8F45`.
- **Grid line:** `#D1C3B2`.
- **Hover surface:** `#E1D7CA`.

## 3. Component Stylings
- **Cards:** `border-radius: 16px`. Background `#1E1E1E`. Internal padding of `20px`. Subtle border: `1px solid #2C2C2E`.
- **Charts:** Grid lines in `#2C2C2E`. Data in `#00E5FF` with `#32D74B` for area gradients. Avoid heavy border lines.
- **Tables:** Rows use `border-bottom: 1px solid #2C2C2E`. Row hover changes the background to `#252525`.
- **Alerts:** Box with background `#3A1C1C`, red text `#FF453A`, and a `4px solid #FF453A` left border.

## 4. Typography
- **Titles:** Inter, semi-bold, 24px.
- **KPI metrics (Watts, kWh, Bs.):** JetBrains Mono or Fira Code, bold, 32px.
- **Body:** Inter Regular, 14px.

## 5. Layout Principles
- **Grid:** 12 columns.
- **Spacing:** Multiples of 8px (8px, 16px, 24px, 32px).
- **Dashboard:** 3-column top view (KPI, KPI, KPI), main chart spanning 8 columns, alerts panel spanning 4 columns on the right.

## 6. Do's and Don'ts
- **Do:** Use area charts to soften consumption spikes.
- **Do:** Always include the Bolivianos equivalent (`Bs.`) next to kWh.
- **Don't:** Use pastel colors or white backgrounds for the default dark monitoring theme because they hurt prolonged data reading. The warm light inspection theme is the only approved exception.
- **Don't:** Use generic light-bulb icons. Prefer lightning, plug, or meter icons.
