# BGG - Which Game Today?
![Static Badge](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)

BGG - Which Game Today? is a board game recommendation assistant that helps you find the perfect game from your owned collection. It uses data from BoardGameGeek (BGG) and provides recommendations based on your preferences. The chatbot interacts with you to understand your requirements and suggests games that match your criteria.

## Requirements
Copy the file `.env.example` to `.env` and fill in the required environment variables. Then you can export the environment variables with the following command:
```bash
source .env
```

First you need an account on [BoardGameGeek](https://boardgamegeek.com/). Add your games to your collection and write your username in the environment variables to `BGG_USERNAME`

## Installation
1. Install Python (at least, version >= 3.11)
2. Install all requirements from `Pipfile` via `pipenv install`

## Usage
Run the script with the `db` command to insert your BGG collection into the database.
```bash
./main.py db
```

After that you can run the script with the `chat` command to let the AI recommend a game for you.
```bash
./main.py chat
```

With the chat option you can choose between using the local AI or the OpenAI API. If you want to use the OpenAI API you need to set the environment variable `USE_OPENAI` to `True` and set the `OPENAI_API_KEY`.


### Flags
- With `-e` (or) `--expansions`: Include expansions in the recommendations. (not recommended)

- With `-f` (or) `--fast`: Skip the detailed chat summary and provide quick game recommendations
f
- With `-v` (or) `--verbose`: increase verbosity

- With `-r` (or) `--refresh`: Refresh data of already known BGG pages



### Environment Variables
The following environment variables are required to run the script:
- `BGG_USERNAME`: Your BoardGameGeek username.
- `USE_OPENAI`: Use OpenAI for chatbot responses (default: False).
- `OPENAI_API_KEY`: Your OpenAI API key.
- `SENTENCE_TRANFORMER_MODEL`: The model name for the sentence transformer (default: all-MiniLM-L6-v2).
- `GPT_CHAT_MODEL`: the model to use for the OpemAPI AI chat (default: gpt-4o-mini). 
- `LOCAL_CHAT_MODEL`: the model to use for the localAI chat (default: meta-llama-3.1-8b-instruct).
- `BGG_COLLECTION_TITLES`: Override default titles with your collection titles (default: True)


## Contributing
Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License
The GNU GENERAL PUBLIC LICENSE. Please have a look at the [LICENSE](LICENSE) for more details.

## Acknowledgements
* [BoardGameGeek](https://boardgamegeek.com/) for providing the game data.
* [LocalAI](https://localai.io/) for the language model.
* [Qdrant](https://qdrant.tech/) for the vector search engine.
