# Memory Tool Roadmap

This document outlines the current status and future plans for the memory tool. It's designed to be a high-level overview of progress and goals.

## Current Status (Done)

*   [x] **Core Tracking:** Captures audio, video, screenshots, and keyboard/mouse inputs.
*   [x] **Window Context:** Groups inputs by the window they occurred in.
*   [x] **Privacy:** Implements privacy filters to censor specific window content and inputs.
*   [x] **Data Storage:** Saves all tracked data to a Postgres database.
*   [x] **LLM Analysis:** Uses an LLM to create observation logs and analyze activity at set intervals and custom prompts.
*   [x] **Text-to-Speech:** Supports TTS for LLM outputs.
*   [x] **LLM Streaming:** Streams and plays LLM responses via TTS.
*   [x] **LLM Media Input:** Sends media to LLM for processing.
*   [x] **Configurable Tools:** Allows adding and using tools for various functionalities, including controlling spotify, accessing recent logs, screen recording and TTS.
*   [x] **Assistant Agent:** Includes an assistant agent that can be interacted with for help.
*   [x] **CLI Interface:** Provides a basic CLI to control tracking and access logs.
*   [x] **Basic Analysis Workflow:** Core workflow of analysis working at 30 sec, 5 min and end of session.
*   [x] **Codebase Refactor:** Initial restructure of the code for async support.

## In Progress

*   [ ] **Analysis Improvement:** Refining the analysis workflow and data processing.
*   [ ] **Code Restructure**: Code quality improvement
*   [ ] **Privacy Enhancement:** Improving privacy filters (Audio)
*   [ ] **Assistant Agent Input:** Making it so the assistant agent can record and receive voice messages.
*   [ ] **Database Migration:** Implementing database schema migrations.

## Upcoming Features (Todo)

*   [ ] **Reminders:** Adding exercise reminders, procrastination notifications, and conditional reminders.
*   [ ] **Prompt Management:** Implementing a prompt gallery for quick application of prompts.
*   [ ] **Task Management:** Adding task creation and management functionality.
*   [ ] **Information View:** Developing a way to visualize and organize the tracked information.
*   [ ] **Contextual Bookmarking:** Adding ability to bookmark moments for later reflection.
*   [ ] **Agent Naming:** Adding names to agents.
*   [ ] **LLM Trigger:** Adding functionality to trigger the LLM by saying a keyword.
*   [ ] **Agent Context:** Make the assistant agent aware of the recent LLM responses and able to query the database for context.
*   [ ] **Agent Tooling**: Add tools to the assistant agent that allow it to perform actions in the real world, e.g., google, open apps, control spotify.
*   [ ] **LLM Response Saving**: Saving the responses of the assistant agent to the database.
*   [ ] **Code Restructure** - Improve codebase structure, models, and how they use tools.
*  [ ] **General Improvements:** Focus on user experience, and overall "quality code"

## Future Ideas (Considerations)

*   [ ] **Context Provider Concept:** Expand the tool to be a central context provider for various applications.
*   [ ] **Personalization Extensions:** Create extensions to personalize web content and use the memory system data.
*   [ ] **Productivity Features:** Add more features to boost productivity and focus, like real-time task tracking.
*   [ ] **Possible P2P functionality between other memory systems**

## Priorities
* 1. Full workflow analysis working
* 2. Full tasks + goals + activities + tracking working
* 3. Integrate better with things - with the hyprassistant, with google calendar api, with each other inside the memory, with extension, etc.
