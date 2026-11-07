import sys
import pkgutil
import re
import pkg_resources
import importlib.metadata
import pickle
import json

from repo_utils import *

std_lib_modules = set(sys.builtin_module_names) | {mod.name for mod in pkgutil.iter_modules()}
installed_packages = {pkg.key: pkg.project_name for pkg in pkg_resources.working_set}

package_name_mapping = {
    # ✅ Scientific Computing & Data Analysis
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "PIL": "pillow",
    "yaml": "pyyaml",
    "pd": "pandas",
    "np": "numpy",
    "mpl": "matplotlib",
    "sns": "seaborn",
    "sp": "scipy",
    "jax": "jaxlib",
    "pytz": "pytz",
    "dateutil": "python-dateutil",
    "statsmodels": "statsmodels",
    "dask": "dask",
    "polars": "polars",
    "openpyxl": "openpyxl",
    "xlrd": "xlrd",
    "xlsxwriter": "xlsxwriter",
    "pyxlsb": "pyxlsb",
    "tabulate": "tabulate",
    "pyarrow": "pyarrow",
    "fastparquet": "fastparquet",

    # ✅ Machine Learning & AI
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    "torch": "torch",
    "jax": "jax",
    "torchvision": "torchvision",
    "torchaudio": "torchaudio",
    "fastai": "fastai",
    "mmcv": "mmcv-full",
    "transformers": "transformers",
    "sentence_transformers": "sentence-transformers",
    "diffusers": "diffusers",
    "spacy": "spacy",
    "nltk": "nltk",
    "gensim": "gensim",
    "timm": "timm",
    "lightgbm": "lightgbm",
    "xgboost": "xgboost",
    "catboost": "catboost",
    "optuna": "optuna",
    "pymc3": "pymc3",
    "prophet": "prophet",

    # ✅ Deep Learning & NLP
    "fairseq": "fairseq",
    "nemo": "nemo-toolkit",
    "onnx": "onnx",
    "onnxruntime": "onnxruntime",
    "sentencepiece": "sentencepiece",
    "apex": "apex",
    "allennlp": "allennlp",

    # ✅ Web Development
    "flask": "flask",
    "django": "django",
    "fastapi": "fastapi",
    "quart": "quart",
    "bottle": "bottle",
    "tornado": "tornado",
    "starlette": "starlette",
    "hug": "hug",
    "sanic": "sanic",
    "responder": "responder",
    "falcon": "falcon",
    "dash": "dash",
    "plotly": "plotly",
    "streamlit": "streamlit",
    "gradio": "gradio",

    # ✅ Web Scraping & HTTP Requests
    "requests": "requests",
    "httpx": "httpx",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "scrapy": "scrapy",
    "selenium": "selenium",
    "mechanize": "mechanize",
    "pyppeteer": "pyppeteer",
    "html5lib": "html5lib",
    "tldextract": "tldextract",

    # ✅ Data Serialization & Parsing
    "yaml": "pyyaml",
    "toml": "tomli",
    "jsonschema": "jsonschema",
    "msgpack": "msgpack",
    "ujson": "ujson",
    "orjson": "orjson",
    "cbor2": "cbor2",
    "avro": "fastavro",

    # ✅ Database & ORMs
    "psycopg2": "psycopg2",
    "sqlalchemy": "sqlalchemy",
    "pymysql": "pymysql",
    "redis": "redis",
    "mongoengine": "mongoengine",
    "pymongo": "pymongo",
    "cassandra": "cassandra-driver",
    "elasticsearch": "elasticsearch",
    "tinydb": "tinydb",
    "dataset": "dataset",
    "supabase": "supabase",

    # ✅ Async & Networking
    "aiohttp": "aiohttp",
    "asyncio": "asyncio",
    "websockets": "websockets",
    "trio": "trio",
    "socketio": "python-socketio",
    "twisted": "twisted",
    "pyzmq": "pyzmq",

    # ✅ CLI & Terminal Tools
    "click": "click",
    "rich": "rich",
    "prompt_toolkit": "prompt-toolkit",
    "pyfiglet": "pyfiglet",
    "colorama": "colorama",
    "curses": "windows-curses",
    "blessed": "blessed",

    # ✅ Security & Cryptography
    "cryptography": "cryptography",
    "pyjwt": "pyjwt",
    "bcrypt": "bcrypt",
    "passlib": "passlib",
    "pycryptodome": "pycryptodome",
    "paramiko": "paramiko",

    # ✅ Logging & Debugging
    "loguru": "loguru",
    "debugpy": "debugpy",
    "icecream": "icecream",
    "traceback2": "traceback2",
    "pdbpp": "pdbpp",
    
    # ✅ Automation & DevOps
    "fabric": "fabric",
    "invoke": "invoke",
    "ansible": "ansible",
    "pyinfra": "pyinfra",
    "pexpect": "pexpect",

    # ✅ Audio, Video & Image Processing
    "pydub": "pydub",
    "moviepy": "moviepy",
    "imageio": "imageio",
    "soundfile": "soundfile",
    "librosa": "librosa",
    "torchaudio": "torchaudio",
    "wave": "wave",
    "mutagen": "mutagen",
    "mediapipe": "mediapipe",
    "face_recognition": "face-recognition",
    "deepface": "deepface",

    # ✅ Game Development
    "pygame": "pygame",
    "panda3d": "panda3d",
    "arcade": "arcade",
    "pyglet": "pyglet",
    "ursina": "ursina",

    # ✅ Miscellaneous
    "pyperclip": "pyperclip",
    "tqdm": "tqdm",
    "pynput": "pynput",
    "validators": "validators",
    "pyautogui": "pyautogui",
    "mypy": "mypy",
    "mimesis": "mimesis",
    "faker": "faker",
    "arrow": "arrow",
    "shapely": "shapely",
}


pattern = r'^\s*import\s+([a-zA-Z_][\w\.]*)|' \
          r'^\s*from\s+([a-zA-Z_][\w\.]+)\s+import\s+'

def extract_pip_packages(code):
    matches = re.findall(pattern, code, re.MULTILINE)
    
    imported_packages = {pkg.split('.')[0] for match in matches for pkg in match if pkg}

    pip_packages = set()
    for pkg in imported_packages:
        normalized_pkg = pkg.lower() 
        if normalized_pkg in installed_packages:
            pip_packages.add(installed_packages[normalized_pkg])
        elif pkg in package_name_mapping:
            pip_packages.add(package_name_mapping[pkg])

    return pip_packages


def read_python_file(file_path):
    if not os.path.exists(file_path):
        print(f"File '{file_path}' does not exist.")
        return None
    
    encodings = ['utf-8', 'latin-1', 'utf-16', 'iso-8859-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                return file.read()
        except (UnicodeDecodeError, IOError) as e:
            if encoding == encodings[-1]:
                print(f"Error reading the file '{file_path}': {e}")
                return None

    return None



def scan_directory(directory):
    all_libraries = set()

    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            ext = filename.split('.')[-1]

            if ext in ['py']:
                code = read_python_file(os.path.join(dirpath, filename))
                if code is not None:
                    all_libraries.update(extract_pip_packages(code))

    return all_libraries


def read_pickle_file(file_path: str):
    try:
        with open(file_path, "rb") as file:
            data = pickle.load(file)
        return data
    except Exception as e:
        print(f"Error reading pickle file: {e}")
        return None


def write_dict_to_json(dictionary, file_path):
    try:
        with open(file_path, 'w', encoding='utf-8') as json_file:
            json.dump(dictionary, json_file, ensure_ascii=False, indent=4)
        print(f"Dictionary successfully written to {file_path}")
    except IOError as e:
        print(f"Error writing to file {file_path}: {e}")


urls_path_pkl = '/home/abra165f/ws_code_reuse/LPWC_Extension/Creating_LPWC_Snapshot/data/urls.pkl'

urls = read_pickle_file(urls_path_pkl)


for url in urls:
    print("===========================================================")
    repo_path_local = download_github_repo(url, "/home/abra165f/ws_code_reuse/LPWC_Extension/Extract_Libraries/downloaded_repo_temp")

    if repo_path_local:
        libraries = scan_directory(repo_path_local)

        if libraries:
            username, repo_name = url.split('/')[-2], url.split('/')[-1]

            pack_data = {
                "url": url,
                "used_package": list(libraries)
            }

            filename = username + "_" + repo_name + ".json"

            save_json_path = os.path.join('/home/abra165f/ws_code_reuse/LPWC_Extension/Extract_Libraries/package_data', filename)
            write_dict_to_json(pack_data, save_json_path)

        delete_directory(repo_path_local)

    print("===========================================================")