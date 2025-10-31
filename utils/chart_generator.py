# sql-agent-pro/utils/chart_generator.py
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import difflib
from typing import Optional, Tuple, List, Dict, Any
from config.settings import CHART_TYPES


def sanitize_spec(df: pd.DataFrame, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize chart specification by mapping column names"""
    if not isinstance(spec, dict):
        return {}
    s = dict(spec)
    # Accept common aliases from LLMs/users
    if 'category' in s and 'names' not in s: 
        s['names'] = s.pop('category')
    if 'label' in s and 'names' not in s: 
        s['names'] = s.pop('label')
    if 'value' in s and 'values' not in s: 
        s['values'] = s.pop('value')
    if 'count' in s and 'values' not in s: 
        s['values'] = s.pop('count')

    # Choropleth aliases
    if 'location' in s and 'locations' not in s: 
        s['locations'] = s.pop('location')
    if 'state' in s and 'locations' not in s: 
        s['locations'] = s.pop('state')
    if 'country' in s and 'locations' not in s: 
        s['locations'] = s.pop('country')

    if s.get("type") == "choropleth":
        # Try to find color column from various aliases
        if 'value' in s and 'color' not in s: 
            s['color'] = s.pop('value')
        if 'y' in s and 'color' not in s: 
            s['color'] = s.pop('y')
        if 'values' in s and 'color' not in s: 
            s['color'] = s.pop('values')
        
        # Validate locationmode and scope
        if 'locationmode' not in s or not s['locationmode']:
            # Try to auto-detect from locations column
            loc_col = s.get('locations')
            if loc_col and loc_col in df.columns:
                sample = df[loc_col].dropna().astype(str).str.upper().head(5).tolist()
                us_states = ['CA', 'TX', 'NY', 'FL', 'IL']  # Common US states
                if any(state in sample for state in us_states):
                    s['locationmode'] = 'USA-states'
                    s['scope'] = 'usa'
                else:
                    s['locationmode'] = 'country names'
                    s['scope'] = 'world'
        
        # Ensure scope matches locationmode
        if s.get('locationmode') == 'USA-states' and 'scope' not in s:
            s['scope'] = 'usa'
        elif s.get('locationmode') in ('country names', 'ISO-3') and 'scope' not in s:
            s['scope'] = 'world'
        
    for k in ["x","y","color","names","values","lat","lon","locations"]:
        if k in s and s[k] is not None:
            fixed = _closest_col(df, s[k])
            s[k] = fixed
    if isinstance(s.get("path"), list):
        s["path"] = [ _closest_col(df, c) for c in s["path"] if isinstance(c, str) and _closest_col(df, c) ]
    return s

def detect_desired_chart(question: str) -> Optional[str]:
    """Detect desired chart type from question text"""
    q = (question or "").lower()
    # Priority: honor explicit pie/donut requests even if 'distribution' is present.
    if "donut" in q or "doughnut" in q:
        return "donut"
    if "pie chart" in q or q.strip().startswith("pie") or " pie " in q:
        return "pie"
    mapping = {
        "line": ["line chart", "linegraph", "line plot", "time series", "timeseries", "trend"],
        "bar": ["bar chart", "barplot", "bar graph"],
        "area": ["area chart", "area graph"],
        "scatter": ["scatter", "scatterplot", "scatter plot"],
        "histogram": ["histogram", "distribution"],
        "box": ["boxplot", "box plot"],
        "violin": ["violin"],
        "corr_heatmap": ["correlation", "heatmap"],
        "treemap": ["treemap"],
        "pareto": ["pareto"],
        "map_geo": ["map", "geo", "latitude", "longitude"],
        "choropleth": ["choropleth"]
    }
    for typ, keys in mapping.items():
        if any(k in q for k in keys):
            return typ
    return None

def _first_numeric(df):
    """Find first numeric column in dataframe"""
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            return c
    return None

def _first_categorical(df):
    """Find first categorical column in dataframe"""
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique(dropna=True) <= 50:
            return c
    return None

def choose_fallback_spec(df: pd.DataFrame, question: str) -> Dict[str, Any]:
    """Choose fallback chart specification"""
    dt_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if dt_cols and num_cols:
        return {"type": "line", "x": dt_cols[0], "y": num_cols[0]}
    x = _first_categorical(df); y = _first_numeric(df)
    if x and y:
        return {"type": "bar", "x": x, "y": y, "aggregate": "sum", "top_n": 20}
    if len(num_cols) >= 2:
        return {"type": "corr_heatmap"}
    if len(num_cols) == 1:
        return {"type": "histogram", "x": num_cols[0], "bins": 30}
    if len(df.columns) > 0 and df[df.columns[0]].nunique(dropna=True) <= 12:
        c = df.columns[0]
        return {"type": "pie", "names": c, "values": "count"}
    return {}

def reason_for_spec(df: pd.DataFrame, spec: Dict[str, Any], question: str) -> str:
    """Generate reasoning for chart specification"""
    typ = (spec.get("type") or "").lower()
    x = spec.get("x"); y = spec.get("y")
    msg = ""
    if typ == "line":
        msg = "A line chart highlights trends over an ordered x-axis"
        if x: msg += f" (**{x}**)"
        if y: msg += f" for **{y}**"
        msg += "."
    elif typ == "bar":
        msg = "A bar chart compares a numeric measure across categories"
        if x: msg += f" (**{x}**)"
        if y: msg += f" for **{y}**"
        msg += "."
    elif typ == "histogram":
        msg = f"A histogram shows the distribution of **{spec.get('x','a numeric field')}**."
    elif typ == "scatter":
        msg = f"A scatter plot shows relationship between **{x}** and **{y}**."
    elif typ == "corr_heatmap":
        msg = "A correlation heatmap summarizes pairwise relationships among numeric columns."
    elif typ == "box":
        msg = f"A box plot shows distribution of **{y}** by **{x}** with medians and spread."
    elif typ == "violin":
        msg = f"A violin plot shows distribution density of **{y}** by **{x}**."
    elif typ in ("pie","donut"):
        msg = f"A {typ.replace('_',' ')} shows the share of **{spec.get('values','value')}** by **{spec.get('names','category')}**."
    elif typ == "area":
        msg = f"An area chart emphasizes cumulative magnitude of **{y}** over **{x}**."
    elif typ == "treemap":
        msg = "A treemap shows hierarchical composition across a path of categorical fields."
    elif typ == "pareto":
        msg = f"A Pareto chart shows contribution of **{y}** by **{x}** and cumulative percentage."
    elif typ == "map_geo":
        msg = "A geo scatter map shows the spatial distribution of points using latitude/longitude."
    elif typ == "choropleth":
        msg = "A choropleth maps numeric intensity by region."
    else:
        msg = "This chart best fits the columns returned for your question."
    return f"🤖 Why this chart: {msg}"

def coerce_type(spec: Dict[str, Any], desired: str) -> Dict[str, Any]:
    """Coerce chart specification to desired type"""
    s = dict(spec)
    s["type"] = desired
    
    # Smart mapping to convert between chart families
    if desired in ("pie", "donut"):
        # If coercing *to* a pie, map x/y *to* names/values
        if "x" in s and "names" not in s:
            s["names"] = s.pop("x")
        if "y" in s and "values" not in s:
            s["values"] = s.pop("y")
    
    elif desired in ("bar", "line", "area", "scatter"):
        # If coercing *to* an XY chart, map names/values *to* x/y
        if "names" in s and "x" not in s:
            s["x"] = s.pop("names")
        if "values" in s and "y" not in s:
            s["y"] = s.pop("values")

    elif desired == "choropleth":
        # Map x/y from a fallback (like a bar chart) to locations/color
        if "x" in s and "locations" not in s:
            s["locations"] = s.pop("x")
        if "y" in s and "color" not in s:
            s["color"] = s.pop("y")
        
        # CRITICAL: If we are coercing, we must also add default
        # location information, or the renderer will fail.
        # We assume USA-states as it's the most common for this data.
        if "locationmode" not in s:
            s["locationmode"] = "USA-states"
        if "scope" not in s and s["locationmode"] == "USA-states":
            s["scope"] = "usa"
    
    return s

def build_primary_and_alts(df: pd.DataFrame, chart_spec: Dict[str, Any], question: str) -> Tuple[Optional[go.Figure], List[Tuple[str, go.Figure]], Dict[str, Any]]:
    """Build primary and alternative charts from specification"""
    desired = detect_desired_chart(question)
    final_spec = {"primary": {}, "alternates": [], "reasoning": ""}

    primary_spec = sanitize_spec(df, (chart_spec.get("primary") or {}))
    if desired and primary_spec:
        coerced = coerce_type(primary_spec, desired)
        fig = render_chart(df, coerced)
        if fig:
            final_spec["primary"] = coerced
            final_spec["reasoning"] = reason_for_spec(df, coerced, question)
            alts_out = []
            for alt in (chart_spec.get("alternates") or [])[:3]:
                sani = sanitize_spec(df, alt)
                f = render_chart(df, sani)
                if f:
                    name = alt.get("name") or alt.get("type") or "Alt"
                    alts_out.append((name.title(), f))
                    final_spec["alternates"].append(sani)
            return fig, alts_out, final_spec

    if primary_spec:
        fig = render_chart(df, primary_spec)
        if fig:
            final_spec["primary"] = primary_spec
            final_spec["reasoning"] = reason_for_spec(df, primary_spec, question)
            alts_out = []
            for alt in (chart_spec.get("alternates") or [])[:3]:
                sani = sanitize_spec(df, alt)
                f = render_chart(df, sani)
                if f:
                    name = alt.get("name") or alt.get("type") or "Alt"
                    alts_out.append((name.title(), f))
                    final_spec["alternates"].append(sani)
            return fig, alts_out, final_spec

    alts_out = []
    promo = None
    for alt in (chart_spec.get("alternates") or [])[:3]:
        sani = sanitize_spec(df, alt)
        if desired:
            coerced = coerce_type(sani, desired)
            f = render_chart(df, coerced)
            if f and promo is None:
                promo = coerced; pf = f
                continue
        f = render_chart(df, sani)
        if f and promo is None:
            promo = sani; pf = f
            continue
        if f:
            name = alt.get("name") or alt.get("type") or "Alt"
            alts_out.append((name.title(), f))
            final_spec["alternates"].append(sani)

    if promo:
        final_spec["primary"] = promo
        final_spec["reasoning"] = reason_for_spec(df, promo, question)
        return pf, alts_out, final_spec

    fb = choose_fallback_spec(df, question)
    if desired:
        fb = coerce_type(fb, desired) if fb else {"type": desired}
    fig = render_chart(df, fb)
    if fig:
        final_spec["primary"] = fb
        final_spec["reasoning"] = reason_for_spec(df, fb, question)
        return fig, alts_out, final_spec

    return None, [], final_spec



def _closest_col(df: pd.DataFrame, name: Any) -> Optional[str]:
    """Find closest column name in dataframe"""
    if not isinstance(name, str):
        return None
    cols = list(df.columns)
    for c in cols:
        if c.lower() == name.lower():
            return c
    m = difflib.get_close_matches(name, cols, n=1, cutoff=0.6)
    return m[0] if m else None

def _sg(df: pd.DataFrame, name: Any) -> Optional[str]:
    """Safe get column name from dataframe"""
    return name if isinstance(name, str) and name in df.columns else None

def _normalize_line_axes(_df: pd.DataFrame, _x: Optional[str], _y: Optional[str]) -> Tuple[pd.DataFrame, Optional[str], Optional[str]]:
    """Normalize axes for line charts"""
    if not _y or _y not in _df.columns:
        return _df, _x, _y
    if _x and _x in _df.columns:
        if not pd.api.types.is_datetime64_any_dtype(_df[_x]):
            try:
                parsed = pd.to_datetime(_df[_x], errors="coerce")
                if parsed.notna().mean() > 0.6:
                    _df = _df.copy()
                    _df[_x] = parsed
            except Exception:
                pass
        if _df[_x].isna().all():
            _x = None
    if not _x:
        _df = _df.reset_index().rename(columns={"index": "_idx"})
        _x = "_idx"
    _df = _df.dropna(subset=[_y])
    return _df, _x, _y

def render_chart(df: pd.DataFrame, spec: Dict[str, Any]) -> Optional[go.Figure]:
    """Render chart based on specification - COMPLETE VERSION"""
    typ = (spec.get("type") or "").strip()
    if not typ or typ not in CHART_TYPES:
        return None

    x      = _sg(df, spec.get("x"))
    y      = _sg(df, spec.get("y"))
    color  = _sg(df, spec.get("color"))
    names  = _sg(df, spec.get("names"))
    values = _sg(df, spec.get("values"))

    agg = (spec.get("aggregate") or "").lower()
    top_n = int(spec.get("top_n") or 0)
    sort_desc = bool(spec.get("sort_desc", True))

    work = df.copy()

    if x and not pd.api.types.is_numeric_dtype(work[x]) and work[x].nunique(dropna=True) > 30:
        top_vals = work[x].value_counts(dropna=True).head(30).index
        work = work[work[x].isin(top_vals)]

    def _maybe_aggregate(_df: pd.DataFrame) -> pd.DataFrame:
        if agg and x and y and x in _df.columns and y in _df.columns:
            gb = _df.groupby(x, dropna=False)[y]
            if agg == "sum":         _df = gb.sum().reset_index()
            elif agg in {"mean","avg"}: _df = gb.mean().reset_index()
            elif agg == "count":     _df = gb.count().reset_index()
            elif agg == "median":    _df = gb.median().reset_index()
        return _df

    if typ in ("line", "area"):
        if not y:
            return None
        work, x, y = _normalize_line_axes(work, x, y)
        if not x:
            return None
        work = work.sort_values(x)
        fig = px.line(work, x=x, y=y) if typ == "line" else px.area(work, x=x, y=y)
        fig.update_layout(title=f"{y} over {x}", height=420)
        return fig

    if typ == "bar":
        if not (x and y): return None
        work = _maybe_aggregate(work)
        if top_n > 0 and x in work.columns and y in work.columns:
            work = work.sort_values(y, ascending=not sort_desc).head(top_n)
        fig = px.bar(work, x=x, y=y, color=color)
        fig.update_layout(title=f"{y} by {x}", height=420, xaxis_tickangle=-35)
        return fig

    if typ == "stacked_bar":
        if not (x and y and color): return None
        work = _maybe_aggregate(work)
        fig = px.bar(work, x=x, y=y, color=color, barmode="stack")
        fig.update_layout(title=f"{y} by {x}, stacked by {color}", height=420, xaxis_tickangle=-35)
        return fig

    if typ == "histogram":
        hx = spec.get("x")
        if not (hx and hx in df.columns): return None
        fig = px.histogram(work, x=hx, nbins=int(spec.get("bins") or 30))
        fig.update_layout(title=f"Distribution of {hx}", height=420)
        return fig

    if typ == "box":
        if not (x and y): return None
        fig = px.box(work, x=x, y=y, points=False)
        fig.update_layout(title=f"Box plot of {y} by {x}", height=420, xaxis_tickangle=-35)
        return fig

    if typ == "violin":
        if not (x and y): return None
        fig = px.violin(work, x=x, y=y, box=True, points=False)
        fig.update_layout(title=f"Violin plot of {y} by {x}", height=420, xaxis_tickangle=-35)
        return fig

    if typ == "scatter":
        if not (x and y): return None
        fig = px.scatter(work, x=x, y=y, color=color)
        fig.update_layout(title=f"{y} vs {x}", height=420)
        return fig

    if typ == "scatter_trend":
        if not (x and y): return None
        try:
            fig = px.scatter(work, x=x, y=y, trendline="ols", color=color)
        except Exception:
            fig = px.scatter(work, x=x, y=y, color=color)
        fig.update_layout(title=f"{y} vs {x} (trendline)", height=420)
        return fig

    if typ in ("pie", "donut"):
        if not names or names not in work.columns:
            return None # Must have a 'names' column

        # Auto-count if values column is missing or invalid
        if not values or values not in work.columns:
            vc = work[names].dropna().astype(str).value_counts().head(top_n or 20)
            if vc.empty:
                return None
            work = pd.DataFrame({names: vc.index, "count": vc.values})
            values = "count"

        # Coerce non-numeric values column if needed
        if not pd.api.types.is_numeric_dtype(work[values]):
            coerced = pd.to_numeric(work[values], errors="coerce")
            # Re-assign 'work' to the new dataframe with coerced values
            work = work.assign(**{values: coerced}).dropna(subset=[values])

        # Sort and limit top slices
        top = work.sort_values(values, ascending=False).head(top_n or 20)

        # Create pie or donut chart
        fig = px.pie(top, names=names, values=values, hole=(0.5 if typ == "donut" else 0))
        fig.update_layout(title=f"{values.title()} composition by {names}", height=420)

        return fig

    if typ == "corr_heatmap":
        nums = [c for c in work.columns if pd.api.types.is_numeric_dtype(work[c])]
        if len(nums) < 2: return None
        corr = work[nums].corr(numeric_only=True)
        fig = px.imshow(corr, text_auto=True, aspect="auto", title="Correlation Matrix")
        fig.update_layout(height=500)
        return fig

    if typ == "treemap":
        path = spec.get("path")
        values = spec.get("values")
        if not (isinstance(path, list) and path):
            return None
        clean_path = [p for p in path if p in work.columns]
        values = values if values in work.columns else _first_numeric(work)
        if not (clean_path and values): return None
        fig = px.treemap(work, path=clean_path, values=values, title=f"Treemap by {' > '.join(clean_path)}")
        return fig

    if typ == "pareto":
        if not (x and y): return None
        g = (work.groupby(x, dropna=False)[y]
             .sum().reset_index().sort_values(y, ascending=False))
        g["cum_pct"] = g[y].cumsum() / max(g[y].sum(), 1) * 100.0
        fig = go.Figure()
        fig.add_bar(x=g[x], y=g[y], name=y)
        fig.add_scatter(x=g[x], y=g["cum_pct"], mode="lines+markers", name="Cumulative %", yaxis="y2")
        fig.update_layout(
            title=f"Pareto: {y} by {x}", height=420, xaxis=dict(tickangle=-35),
            yaxis=dict(title=y), yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 100]),
            legend=dict(orientation="h")
        )
        return fig

    if typ == "map_geo":
        lat = spec.get("lat"); lon = spec.get("lon")
        lat = lat if lat in work.columns else _closest_col(work, "lat") or _closest_col(work, "latitude")
        lon = lon if lon in work.columns else _closest_col(work, "lon") or _closest_col(work, "longitude")
        if not (lat and lon): return None
        hover = spec.get("hover_name")
        if hover not in work.columns:
            hover = None
        fig = px.scatter_geo(work, lat=lat, lon=lon, hover_name=hover)
        fig.update_layout(title="Geographic distribution", height=440)
        return fig

    if typ == "choropleth":
        loc = spec.get("locations")
        color_col = spec.get("color")
        
        # CRITICAL FIX 1: Validate columns exist
        if not loc or loc not in work.columns:
            print(f"Choropleth error: 'locations' column '{loc}' not found in dataframe")
            return None
            
        if not color_col or color_col not in work.columns:
            print(f"Choropleth error: 'color' column '{color_col}' not found in dataframe")
            return None
        
        # CRITICAL FIX 2: Get locationmode and scope with better defaults
        locationmode = spec.get("locationmode")
        scope = spec.get("scope")
        
        # Auto-detect if not provided
        if not locationmode:
            # Check if values look like US states
            sample_values = work[loc].dropna().astype(str).str.upper().head(5).tolist()
            us_states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
                        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
                        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
                        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
            
            if any(val in us_states for val in sample_values):
                locationmode = "USA-states"
                scope = "usa"
            else:
                # Default to country names
                locationmode = "country names"
                scope = "world"
        
        # Set default scope if not provided
        if not scope:
            if locationmode == "USA-states":
                scope = "usa"
            else:
                scope = "world"
        
        # CRITICAL FIX 3: Clean and prepare data
        work_clean = work[[loc, color_col]].copy()
        
        # Remove nulls
        work_clean = work_clean.dropna(subset=[loc, color_col])
        
        # Convert location column to string and strip whitespace
        work_clean[loc] = work_clean[loc].astype(str).str.strip()
        
        # CRITICAL FIX 4: Ensure color column is numeric
        if not pd.api.types.is_numeric_dtype(work_clean[color_col]):
            work_clean[color_col] = pd.to_numeric(work_clean[color_col], errors='coerce')
            work_clean = work_clean.dropna(subset=[color_col])
        
        # CRITICAL FIX 5: Aggregate duplicates (in case of multiple rows per location)
        work_clean = work_clean.groupby(loc, as_index=False)[color_col].sum()
        
        if work_clean.empty:
            print("Choropleth error: No valid data after cleaning")
            return None
        
        try:
            # CRITICAL FIX 6: Use correct Plotly parameters
            fig = px.choropleth(
                work_clean, 
                locations=loc, 
                color=color_col,
                locationmode=locationmode,
                scope=scope,
                labels={color_col: color_col.replace('_', ' ').title()},
                color_continuous_scale="Viridis"
            )
            
            fig.update_layout(
                title=f"{color_col.replace('_', ' ').title()} by {loc}",
                height=500,
                geo=dict(
                    showframe=False,
                    showcoastlines=True,
                    projection_type='albers usa' if scope == 'usa' else 'natural earth'
                )
            )
            
            return fig
            
        except Exception as e:
            print(f"Choropleth render error: {e}")
            # Fallback to bar chart
            fig = px.bar(work_clean.head(20), x=loc, y=color_col)
            fig.update_layout(
                title=f"{color_col} by {loc} (Bar Chart - Choropleth Failed)",
                height=420,
                xaxis_tickangle=-45
            )
            return fig

    return None
