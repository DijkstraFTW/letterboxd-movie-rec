import pickle
from datetime import datetime

from astronomer.include.prediction.VAE import VAE
import torch.optim as optim
import torch.nn as nn
import torch
from torch.utils.data import TensorDataset, DataLoader
from sklearn.feature_extraction.text import TfidfVectorizer
import time

class ContentBasedFilteringModel() :

    def get_TFIDF_vectors(self, df_merged):
        start_time = time.time()

        tfidf = TfidfVectorizer(ngram_range=(1, 1), min_df=0.0001, stop_words='english')
        tfidf_matrix = tfidf.fit_transform(df_merged["bag_of_words"])

        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Elapsed time: {elapsed_time:.4f} seconds")

        return tfidf_matrix

    def prepare_trainset(self, tfidf_matrix) :

        batch_size = 32
        tfidf_tensor = torch.tensor(tfidf_matrix.toarray(), dtype=torch.float32)
        dataset = TensorDataset(tfidf_tensor)
        data_loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        return data_loader

    def train_VAE(self, tfidf_tensor, data_loader):

        input_size = tfidf_tensor.size(1)
        hidden_size = 256
        latent_size = 64
        learning_rate = 1e-3
        epochs = 20

        vae = VAE(input_size, hidden_size, latent_size)
        optimizer = optim.Adam(vae.parameters(), lr=learning_rate)
        criterion = nn.BCELoss(reduction='sum')

        for epoch in range(epochs):
            for batch_data in data_loader:

                x = batch_data[0]
                recon_x, mean, logvar = vae(x)
                BCE = criterion(recon_x, x)
                KLD = -0.5 * torch.sum(1 + logvar - mean.pow(2) - logvar.exp())

                # Backward pass and optimization
                loss = BCE + KLD
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            print(f'Epoch [{epoch + 1}/{epochs}], Loss: {loss.item():.4f}')

        print("Model trained successfully !")

        vae.eval()

        model_filename = f"models/vae_{datetime.now().strftime("%Y%m%d%H%M%S")}.pkl"
        with open(model_filename, 'wb') as file:
            pickle.dump(vae, file)

        print(f"Model saved successfully at {model_filename}!")

        return model_filename

    def get_embeddings(self, df_merged, tfidf_tensor, vae):

        embeddings = []

        for i in range(len(df_merged)):
            sample_tfidf_vector = tfidf_tensor[i].unsqueeze(0)
            with torch.no_grad():
                mean, logvar = vae.encoder(sample_tfidf_vector)
            compressed_representation = vae.reparameterize(mean, logvar)
            embeddings.append(compressed_representation.numpy())

        return embeddings

    def get_recommendations(self, title) :

        cosine_sim = "get-cosine-similarity"

        return