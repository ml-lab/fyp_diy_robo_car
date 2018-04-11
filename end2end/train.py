from tf_donkey import Model
import os
from utils import *
from data_generator import DataGenerator
import json

'''
{
"train_text"  : "../data/evened_train.txt",
"trest_text"  : "../data/evened_test.txt",
"name"        : "cnn_test",
"save_dir"    : "donkey_car",
"num_bins"    : 15,
"data_dir"    : "..data/color_120_160",
"in_shape"    : [120, 160, 3],
"message"     : "a simple nn test",
"epochs"      : 1,
"lr"          : 0.001
}
'''

def save_config(save_dir, data_dir, num_bins, lr, batch_size, epochs, in_shape, best_ckpt, message):
    payload = {}
#    payload["name"]        = name
    payload["data_dir"]    = data_dir
    payload["num_bins"]    = num_bins
    payload["lr"]          = lr
    payload["batch_size"]  = batch_size
    payload["epochs"]      = epochs
    payload["in_shape"]    = in_shape
    payload["best_ckpt"]   = best_ckpt
    payload["message"]     = message
    path = os.path.join(save_dir, "config.json")
    
    with open(path, 'a') as f:
        json.dump(payload, f)
    

def main():
    import argparse as argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--train-txt', type=str, required=True)
    parser.add_argument('--test-txt', type=str, required=True)
#    parser.add_argument('--name', type=str, required=True)
    parser.add_argument('--save-dir', type=str, required=True)
    parser.add_argument('--num-bins', type=int, required=True)
    parser.add_argument('--lr', type=float, required=False, default = 0.001)
    parser.add_argument('--batch-size', type=int, required=False, default=50)
    parser.add_argument('--epochs', type=int, required=False, default=10)
    parser.add_argument('--data-dir', type=str, required=True)
    parser.add_argument('--shape', type=int, required=True, nargs=3, help="height width chanels")
    parser.add_argument('--message', type=str, required=True)
    
    args        = parser.parse_args()
    data_dir    = args.data_dir
    image_dir   = os.path.join(data_dir, "images/")
    anno_dir    = os.path.join(data_dir, "annotations/")
    train_path  = args.train_txt
    test_path   = args.test_txt
    
    # Load list of image names for train and test
    raw_train   = load_data(train_path)
    raw_test    = load_data(test_path)
    
    # Aggrigate data into bins
    num_bins    = args.num_bins
    train       = bin_steering_annos(raw_train, num_bins)
    test        = bin_steering_annos(raw_test, num_bins)

    # Create train and test generators
    batch_size  = args.batch_size
    train_gen   = DataGenerator(batch_size=batch_size, 
                      data_set=train,
                      image_dir=image_dir,
                      anno_dir=anno_dir, 
                      num_bins=num_bins)
    
    test_gen    = DataGenerator(batch_size=batch_size, 
                      data_set=test,
                      image_dir=image_dir,
                      anno_dir=anno_dir, 
                      num_bins=num_bins)
    
    # Kick-off
    #name        = args.name
    save_dir    = args.save_dir
    epochs      = args.epochs
    in_shape    = args.shape
    lr          = args.lr
    classes     = [i for i in range(num_bins)]
    car_brain   = Model(save_dir, in_shape, classes=classes)
    best_ckpt   = car_brain.Train(train_gen, test_gen, save_dir=save_dir, epochs=epochs) 
    
    message     = args.message    
    save_config(save_dir, data_dir, num_bins, lr, batch_size, epochs, in_shape, best_ckpt,  message)

if __name__ == "__main__":
    main()