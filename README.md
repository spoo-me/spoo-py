> [!IMPORTANT]
> **This package is deprecated.** py-spoo-url targets the legacy spoo.me endpoints; they keep working, but this package receives no new features or fixes. Its successor is [`spoo`](https://pypi.org/project/spoo/), a fully typed sync and async SDK for the current API:
>
> ```bash
> pip install spoo
> ```
>
> See the [migration guide](https://github.com/spoo-me/spoo-py/blob/main/MIGRATION.md) for a mapping of every py-spoo-url call to its replacement.

<p align=center>
    <img src="https://raw.githubusercontent.com/spoo-me/py_spoo_url/main/assets/py_spoo_url.png" height="50px" alt="py_spoo_url banner">
</p>


### 🚀 Simple URL shortening with advanced analytics, emoji aliases, and more using spoo.me

<br>

<details>
<summary>📖 Table of Contents</summary>

- [📦 Installing](#-installing)
- [📥 Importing](#-importing)
- [✂️ Shortening URL](#️-shortening-url)
  - [For Non-emoji aliases](#for-non-emoji-aliases)
  - [😎 For Emoji aliases](#-for-emoji-aliases)
- [📊 URL Statistics](#-url-statistics)
  - [🔧 Initializing the class](#-initializing-the-class)
  - [👀 Viewing the Basic Statistics](#-viewing-the-basic-statistics)
  - [](#)
    - [Example Usage](#example-usage)
  - [📈 Generating Insightful Charts](#-generating-insightful-charts)
  - [](#-1)
    - [Valid Data that can be passed to make the chart](#valid-data-that-can-be-passed-to-make-the-chart)
    - [Valid Chart types](#valid-chart-types)
    - [Usage Example](#usage-example)
    - [👀 Heatmap Preview](#-heatmap-preview)
- [📤 Exporting Stats Data](#-exporting-stats-data)
- [🧳 Dependencies](#-dependencies)
- [🚨 Error Codes](#-error-codes)
- [🤝 Support and Issues](#-support-and-issues)
- [🤗 Contributing](#-contributing)
- [📜 Licence](#-licence)

</details>

---

## 📦 Installing

You can install this package using pip:

```bash
pip install py_spoo_url
```

---

## 📥 Importing

```python
from py_spoo_url import Shorten, Statistics
```

## ✂️ Shortening URL

### For Non-emoji aliases

```python
shortener = Shortener()
long_url = "https://www.example.com"
short_url = shortener.shorten(long_url, password="SuperSecretPassword@444", max_clicks=100)
# for custom alias, put `alias=<your_choice>`

print(f"Shortened URL: {short_url}")
```

### 😎 For Emoji aliases

```python
shortener = Shortener()
long_url = "https://www.example.com"
emoji_url = shorten.emojify(long_url) # pass password and max-clicks as shown above if you want
# for custom emoji alias, put `emoji_alias=<random_emoji_sequence>`

print(f"Emojified URL: {emoji_url}")
```

**Note:** The emoji sequence must contain actual emojies like `😆🤯...`

---

## 📊 URL Statistics

The Statistics class enables you to retrieve detailed statistics for a given short code.

### 🔧 Initializing the class

```python
from spoo_me import Statistics

# Initialize Statistics with a short code
stats = Statistics(short_code="ga") # replace with the shortcode you want
# if the shortUrl is password protected you have to pass the password too
```

### 👀 Viewing the Basic Statistics

```python
print(f"Total Clicks: {stats.total_clicks}")
print(f"Total Unique Clicks: {stats.total_unique_clicks}")
print(f"Average Daily Clicks: {stats.average_daily_clicks}")
print(f"Clicks Analysis: {stats.clicks_analysis}")
print(f"Browser Analysis: {stats.browsers_analysis}")
# ... and more (details below)
```

<details>

<summary> List of the analytics you can access </summary>

###

| **Method/Attribute** | **Description** |
|------------------------------------|---------------------------------------------------------|
| total_clicks | Total number of clicks on the short URL. |
| total_unique_clicks | Total number of unique clicks on the short URL. |
| average_daily_clicks | Average number of clicks per day. |
| average_monthly_clicks | Average number of clicks per month. |
| average_weekly_clicks | Average number of clicks per week. |
| last_click | Information about the last click on the short URL. |
| last_click_browser | Browser used for the last click. |
| last_click_platform | Operating system used for the last click. |
| created_at | Date when the short URL was created. |
| creation_time | Time of day when the short URL was created. |
| browsers_analysis | Analysis of browsers used for clicks. |
| platforms_analysis | Analysis of operating systems used for clicks. |
| country_analysis | Analysis of countries from which clicks originated. |
| referrers_analysis | Analysis of referrers (sources) of clicks. |
| clicks_analysis | Detailed analysis of daily clicks. |
| unique_browsers_analysis | Analysis of unique browsers used for clicks. |
| unique_platforms_analysis | Analysis of unique operating systems for clicks. |
| unique_country_analysis | Analysis of unique countries from which clicks originated. |
| unique_referrers_analysis | Analysis of unique referrers (sources) of clicks. |
| unique_clicks_analysis | Detailed analysis of daily unique clicks. |
| expired | Indicates if the short URL has expired. |
| password | Password associated with the short URL (if any). |

#### Example Usage

```python
print(f"Creation Time: {stats.creation_time}")
```

</details>

### 📈 Generating Insightful Charts

```python
plt = stats.make_chart(data="browsers_analysis", chart_type="bar") # this returns an object of matplotlib
plt.show()

# ... and more (see below)

# generating countries heatmaps
plt = stats.make_countries_heatmap()
plt.savefig("heatmap.png", format="png", bbox_inches="tight", pad_inches=0.5, dpi=300,)

plt = stats.make_unique_countries_heatmap()
plt.savefig("unique_heatmap.png", format="png", bbox_inches="tight", pad_inches=0.5, dpi=300,)
```

<details>
<summary> List of Available Charts </summary>

###

| Method | Description |
|--------------------------|---------------------------------------------------------|
| make_chart | Create various types of charts based on the data provided. |

| Parameters | Description |
|--------------------------|---------------------------------------------------------|
| data | Type of data to visualize (e.g., 'browsers_analysis', see below). |
| chart_type | Type of chart to create (e.g., "bar", "pie", "line", see below). |
| days | Number of days to consider for time-based analysis. (only for `last_n_days_analysis` and `last_n_days_unique_analysis`) |

#### Valid Data that can be passed to make the chart

- `'browsers_analysis'`
- `'platforms_analysis'`
- `'country_analysis'`
- `'referrers_analysis'`
- `'clicks_analysis'`
- `'unique_browsers_analysis'`
- `'unique_platforms_analysis'`
- `'unique_country_analysis'`
- `'unique_referrers_analysis'`
- `'unique_clicks_analysis'`
- `'last_n_days_analysis'`
- `'last_n_days_unique_analysis'`

#### Valid Chart types

- 'bar'
- 'pie'
- 'line'
- 'scatter'
- 'hist'
- 'box'
- 'area'

#### Usage Example

```python
plt = stats.make_chart('browsers_analysis', chart_type="bar")
plt.show()
```

</details>

#### 👀 Heatmap Preview

<img src="https://raw.githubusercontent.com/spoo-me/py_spoo_url/main/assets/heatmap-example.png" alt="Heatmap Example Image">

## 📤 Exporting Stats Data

You can export the statistical data to various file formats, including Excel, CSV, and JSON:

```python
# Export data to Excel
stats.export_data(filename="stats_export.xlsx", filetype="xlsx")

# Export data to CSV and compress into a ZIP file
stats.export_data(filename="stats_export", filetype="csv")

# Export data to Json
stats.export_data(filename="stats_export.json", filetypes="json")
```

---

## 🧳 Dependencies

- `matplotlib`: For creating charts and visualizations.
- `requests`: For making HTTP requests to the Spoo.me API.
- `pandas`: For handling and manipulating data in tabular form. 🐼
- `geopandas`: For creating geographical visualizations. 🌎

**All of the dependencies are automatically installed while installing the package but in case of any errors, you can install all of the dependencies listed in the `requirements.txt` file.**

## 🚨 Error Codes

To see the error codes returned by the API, please visit [https://spoo.me/api](https://spoo.me/api)

## 🤝 Support and Issues

If you encounter any issues or have questions about using the Spoo.me Python package, please open an issue on the GitHub repository.

## 🤗 Contributing

Contributions are welcome! If you have ideas for improvements or new features, feel free to fork the repository, make your changes, and submit a pull request

## 📜 Licence

This package is licensed under the MIT License - see the LICENSE file for details.

---
![PyPI](https://img.shields.io/pypi/v/py_spoo_url?style=flat-square)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/spoo-me/py_spoo_url/ci.yml)
![Codecov](https://img.shields.io/codecov/c/github/spoo-me/py_spoo_url)
![Downloads](https://img.shields.io/pypi/dm/py_spoo_url?style=flat-square)
![Last Commit](https://img.shields.io/github/last-commit/spoo-me/py_spoo_url?style=flat-square)

---

<h6 align="center">
<img src="https://spoo.me/static/images/favicon.png" height=30>
<br>
© spoo.me . 2025

All Rights Reserved</h6>

<p align="center">
	<a href="https://github.com/spoo-me/py_spoo_url/blob/master/LICENSE.txt"><img src="https://img.shields.io/static/v1.svg?style=for-the-badge&label=License&message=MIT&logoColor=d9e0ee&colorA=363a4f&colorB=b7bdf8"/></a>
</p>
