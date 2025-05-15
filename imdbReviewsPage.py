import os
import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import pandas as pd
import plotly.graph_objects as go
import modals  # your sentiment analysis module

# ————————————————
# CONFIGURATION
# ————————————————
# OMDb API key (set in environment)
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "3d8a59a5")
OMDB_BASE_URL = "http://www.omdbapi.com/"

# ————————————————
# EMOJI LOOKUP
# ————————————————
getEmoji = {
    "happy"    : "😊",
    "neutral"  : "😐",
    "sad"      : "😔",
    "disgust"  : "🤢",
    "surprise" : "😲",
    "fear"     : "😨",
    "angry"    : "😡",
    "positive" : "🙂",
    "negative" : "☹️",
}

# ————————————————
# OMDB HELPERS
# ————————————————
def search_movies_omdb(title, limit=10):
    """
    Search movies using OMDb's s= parameter. Returns list of up to 'limit' dicts.
    """
    params = {"apikey": OMDB_API_KEY, "s": title}
    resp = requests.get(OMDB_BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    if data.get("Response") == "False":
        st.error(data.get("Error", "Search failed"))
        return []
    movies = data.get("Search", [])[:limit]
    return movies


def get_movie_details_omdb(imdb_id):
    """
    Get full details for a single movie by IMDb ID (including full Plot).
    """
    params = {"apikey": OMDB_API_KEY, "i": imdb_id, "plot": "full"}
    resp = requests.get(OMDB_BASE_URL, params=params)
    resp.raise_for_status()
    return resp.json()

# ————————————————
# UTILITY FUNCTIONS
# ————————————————
def plotPie(labels, values):
    base_colors = {
        "happy": "#FFD700",     # gold
        "neutral": "#A9A9A9",   # dark gray
        "sad": "#1E90FF",       # dodger blue
        "disgust": "#8FBC8F",   # dark sea green
        "surprise": "#FF69B4",  # hot pink
        "fear": "#8A2BE2",      # blue violet
        "angry": "#DC143C",     # crimson
        "positive": "#32CD32",  # lime green
        "negative": "#FF4500",  # orange red
    }

    expanded_labels = []
    expanded_values = []
    expanded_colors = []

    for label, value in zip(labels, values):
        parts = [e.strip().lower() for e in label.split("-")]
        split_value = value / len(parts)  # equally divide value among parts
        for part in parts:
            expanded_labels.append(part.capitalize())
            expanded_values.append(split_value)
            expanded_colors.append(base_colors.get(part, "#CCCCCC"))

    fig = go.Figure(
        go.Pie(
            labels=expanded_labels,
            values=[v * 100 for v in expanded_values],
            hoverinfo="label+percent",
            textinfo="value",
            marker=dict(colors=expanded_colors),
        )
    )
    st.plotly_chart(fig, use_container_width=True)






def getEmojiString(head):
    return head + " " + "".join(getEmoji.get(e.strip().lower(), "") for e in head.split("-"))


def applyModal(movie, packageName):
    # Combine description and plot for analysis
    desc_text = movie.get("description", "")
    plot_text = movie.get("Plot", "")
    combined_text = (desc_text + " " + plot_text).strip()  # join with space, strip trailing spaces
    
    reviews = [combined_text] if combined_text else []
    
    if packageName == "Flair":
        preds = [modals.flair(r) for r in reviews]
    elif packageName == "Vader":
        preds = [modals.vader(r) for r in reviews]
    elif packageName == "TextBlob":
        preds = [modals.textBlob(r) for r in reviews]
    elif packageName == "Text2emotion":
        preds = [modals.text2emotion(r) for r in reviews]
    else:
        preds = []
    return dict(pd.Series(preds).value_counts())

# ————————————————
# DATA FETCHING & CACHING
# ————————————————
lastSearched = ""
cacheData = ""

def getDataOmdb(movieName):
    search_results = search_movies_omdb(movieName)
    data = []
    for item in search_results:
        imdb_id = item.get("imdbID")
        details = get_movie_details_omdb(imdb_id)
        data.append({
            "title":       details.get("Title", item.get("Title")),
            "year":        details.get("Year", item.get("Year")),
            "image":       details.get("Poster") if details.get("Poster") != "N/A" else None,
            "description": details.get("Plot", ""),
            "Plot":        details.get("Plot", "")
        })
    return json.dumps({"userSearch": movieName, "result": data})

# ————————————————
# STREAMLIT UI
# ————————————————
def displayMovieContent(movie):
    col1, col2 = st.columns([2, 3])
    with col1:
        if movie.get("image"):
            st.image(movie["image"], width=200)
    with col2:
        st.markdown(f"**{movie['title']} ({movie.get('year','')})**")
        st.write(movie.get("description", ""))


def process(movieName, packageName):
    global lastSearched, cacheData
    if lastSearched != movieName:
        cacheData = getDataOmdb(movieName)
        lastSearched = movieName

    js = json.loads(cacheData)
    if not js.get("result"):
        st.warning("No results found.")
        return
    st.markdown("### Results")
    for movie in js["result"]:
        with st.expander(f"{movie['title']} ({movie.get('year','')})"):
            displayMovieContent(movie)
            result = applyModal(movie, packageName)
            keys, vals = list(result.keys()), list(result.values())

            for i in range(0, len(keys), 4):
                cols = st.columns(4)
                for j, key in enumerate(keys[i:i+4]):
                    cols[j].metric(getEmojiString(key), round(vals[i+j], 2))

            st.subheader("Visual Representation")
            total = max(1, len(movie.get("Plot", "")))  # at least one "review"
            plotPie(keys, [v / total for v in vals])
    
    st.markdown("### API Response")
    with st.expander("See JSON Response"):
        st.json(js)


def renderPage():
    st.title("Sentiment Analysis 😊😐😕😡")
    components.html("<hr style='height:3px;background:#333; margin-bottom:10px'/>", height=15)
    st.subheader("IMDb movie plot sentiment analysis via OMDb API")
    movieName   = st.text_input('Movie Name', placeholder='Type a movie title…')
    packageName = st.selectbox('Select Package', ['Flair', 'Vader', 'TextBlob', 'Text2emotion'])
    if st.button('Search'):
        if movieName:
            process(movieName, packageName)
        else:
            st.warning("Please enter a movie name.")

if __name__ == "__main__":
    renderPage()
