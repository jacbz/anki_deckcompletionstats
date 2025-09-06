# Deck Completion Stats for Anki

An Anki add-on that provides comprehensive statistics and progress tracking.

**[View on AnkiWeb](https://ankiweb.net/shared/info/637361797?cb=1757193469006)**

<div align="center">
    <a href="https://ankiweb.net/shared/info/637361797?cb=1757193469006">
        <img src="https://i.imgur.com/MKHa15c.jpeg" width="800" alt="Deck Completion Stats preview"/>
    </a>
</div>

## Features

**Progress Tracking**
- Cumulative progress charts with study forecasting
- Multiple time granularities (days, weeks, months, quarters, years)
- Card template breakdown and completion percentages

**Learning Analytics** 
- Study streak tracking and total time invested
- Learning history and difficulty analysis
- Card status distribution (New, Learning, Review)

**Interactive Interface**
- Modern dark theme with responsive design
- Interactive charts powered by Chart.js
- Deck and note type filtering with persistent settings

## Installation

1. Open Anki and go to **Tools → Add-ons**
2. Click **Get Add-ons...**
3. Enter the add-on code **637361797** when available on AnkiWeb
4. Click **OK** and restart Anki

Access the statistics via **Tools → Deck Completion Stats**.

## Usage

Open the add-on from the Tools menu. Select a deck and note type to analyze. Settings are automatically saved.

## Development

A VS Code task is configured to create a distribution zip file containing all project files while respecting `.gitignore` rules.

To create a `deckcompletionstats.zip` file:

1. **Option 1**: Use Command Palette
   - Press `Cmd+Shift+P` (macOS) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "Tasks: Run Task"
   - Select "createZip"

2. **Option 2**: Use the Terminal menu
   - Go to Terminal → Run Task → createZip

## Privacy

All data processing occurs locally within Anki. No data is sent to external servers.

## License

Licensed under the Apache License 2.0.
