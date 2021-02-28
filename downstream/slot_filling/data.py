import torch
import torchaudio
from functools import partial
from torch.utils.data import DataLoader
from torch.nn.utils.rnn import pad_sequence


def collect_audio_batch(batch, split, half_batch_size_wav_len=300000):
    '''Collects a batch, should be list of tuples (audio_path <str>, list of int token <list>) 
       e.g. [(file1,txt1),(file2,txt2),...]
    '''
    def audio_reader(filepath):
        wav, sample_rate = torchaudio.load(filepath)
        return wav.reshape(-1, 1)

    # Bucketed batch should be [[(file1,txt1),(file2,txt2),...]]
    if type(batch[0]) is not tuple:
        batch = batch[0]

    # Make sure that batch size is reasonable
    first_len, first_dim = audio_reader(str(batch[0][0])).shape
    if split == 'train':
        wav_half_condition = (first_dim == 1 and first_len > half_batch_size_wav_len)
        if wav_half_condition and len(batch) > 1:
            batch = batch[:len(batch)//2]

    # Read batch
    file, audio_feat, audio_len, text = [], [], [], []
    with torch.no_grad():
        for b in batch:
            file.append(str(b[0]).split('/')[-1].split('.')[0])
            feat = audio_reader(str(b[0]))
            audio_feat.append(feat)
            audio_len.append(len(feat))
            text.append(torch.LongTensor(b[1]))

    # Descending audio length within each batch
    audio_len, file, audio_feat, text = zip(*[(feat_len, f_name, feat, txt)
                                              for feat_len, f_name, feat, txt in sorted(zip(audio_len, file, audio_feat, text), reverse=True, key=lambda x:x[0])])

    return audio_feat, text, file


def create_dataset(split, tokenizer, name, path, bucketing, batch_size, **kwargs):
    ''' Interface for creating all kinds of dataset'''

    # Recognize corpus
    if name.lower() == "librispeech":
        from .librispeech import LibriDataset as Dataset
    elif name.lower() == "snips":
        from .snips import SnipsDataset as Dataset
    else:
        raise NotImplementedError

    if split == 'train':
        loader_bs = 1 if bucketing else batch_size
        bucket_size = batch_size if bucketing else 1
        dataset = Dataset(path, kwargs['train'], tokenizer, bucket_size)
    else:
        loader_bs = batch_size
        dataset = Dataset(path, kwargs[split], tokenizer, 1)

    return dataset, loader_bs


def load_dataset(split, tokenizer, corpus):
    ''' Prepare dataloader for training/validation'''
    num_workers = corpus.pop('num_workers', 12)
    dataset, loader_bs = create_dataset(split, tokenizer, **corpus)
    collate_fn = partial(collect_audio_batch, split=split)
    dataloader = DataLoader(dataset, batch_size=loader_bs, shuffle=(split == 'train'),
                            collate_fn=collate_fn, num_workers=num_workers)
    return dataloader
