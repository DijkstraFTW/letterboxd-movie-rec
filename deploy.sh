sudo mv /home/ubuntu/app/env /home/ubuntu/app/.env
sudo apt update
sudo apt install python3.10
source /home/ubuntu/app/letterboxd_movie_rec/bin/activate
pip install --upgrade pip
pip install -U scikit-learn
pip install -U pip setuptools wheel Cython
pip install -U scikit-surprise
pip install -U python-dotenv
pip install -r /home/ubuntu/app/requirements.txt