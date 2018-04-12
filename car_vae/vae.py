import cv2
import tensorflow as tf
from tensorflow.python.layers.core import dense, dropout, flatten
from tensorflow.python.layers.convolutional import conv2d, conv2d_transpose
from tensorflow.contrib.layers.python.layers.initializers import xavier_initializer as xavier
from tqdm import trange, tqdm
import numpy as np
import os
import sys
sys.path.append('..')
#from show_graph import show_graph
from metrics import Metrics

class Model:
    def __init__(self, in_shape):
        '''
        classes:  List of class names or integers corrisponding to each class being classified
                  by the network. ie: ['left', 'straight', 'right'] or [0, 1, 2]
        '''
        # Define model
        tf.reset_default_graph()
        self.x = tf.placeholder(tf.float32, shape=[None,]+in_shape, name="input")
        self.y = tf.placeholder(tf.float32, shape=[None,]+in_shape, name="label")
        self.training = tf.placeholder(tf.bool, name="training")
        paddings = tf.constant([[0,0],[4,4],[0,0],[0,0]])
        relu    = tf.nn.relu
        
        with tf.name_scope("encoder"):
            # Padding invector so reconstruction returns to the correct size.                                             h,  w, c
            x_padded = tf.pad(self.x, paddings, "SYMMETRIC")                                                             #128,160, 3
            y_padded = tf.pad(self.y, paddings, "SYMMETRIC")
            # Encoder    in     num   shape  stride    pad                                                              
            enc = conv2d(x_padded, 24,  (5,5), (2,2),  "same", activation=relu, kernel_initializer=xavier(), name="enc1")# 64, 80,24 
            enc = conv2d( enc,   32,  (5,5), (2,2),  "same", activation=relu, kernel_initializer=xavier(), name="enc2")# 32, 40,32
            enc = conv2d( enc,   64,  (5,5), (2,2),  "same", activation=relu, kernel_initializer=xavier(), name="enc3")# 16, 20,64
            enc = conv2d( enc,   64,  (3,3), (2,2),  "same", activation=relu, kernel_initializer=xavier(), name="enc4")#  8, 10,64
            enc = conv2d( enc,   64,  (3,3), (1,1),  "same", activation=relu, kernel_initializer=xavier(), name="enc5")#  8, 10,64
            enc = flatten(enc)
            #             in   num
            enc = dense(  enc, 100, activation=relu, kernel_initializer=xavier(), name="enc6")
            enc = dropout(enc, rate=0.1, training=self.training)
            
            # VAE sampling
            mu        = dense(  enc, 50, activation=relu, kernel_initializer=xavier(), name="mu")
            log_sigma = dense(  enc, 50, activation=relu, kernel_initializer=xavier(), name="log_sigma")
            z_hat     = tf.random_normal(shape=tf.shape(mu))
            z         = mu + tf.exp(log_sigma / 2.) * z_hat
            z         = dropout(z, rate=0.1, training=self.training)
            
        with tf.name_scope("decoder"):
            # Decoder    in           num   
            dec = dense(     z,       100, activation=relu, kernel_initializer=xavier(), name="dec6")
            dec = dense(   dec, (8*10*64), activation=relu, kernel_initializer=xavier(), name="dec7")
            dec  = tf.reshape(dec, (-1,8,10,64))
            #                        in num  shape  stride   pad    
            dec  = conv2d_transpose(dec, 64, (3,3), (1,1), "same", activation=relu, name="dec5")
            dec  = conv2d_transpose(dec, 64, (3,3), (2,2), "same", activation=relu, name="dec4")
            dec  = conv2d_transpose(dec, 32, (5,5), (2,2), "same", activation=relu, name="dec3")
            dec  = conv2d_transpose(dec, 24, (5,5), (2,2), "same", activation=relu, name="dec2")
            dec  = conv2d_transpose(dec, 3,  (5,5), (2,2), "same", activation=relu, name="dec1")
            
            # # VAE Loss    
            # 1. Reconstruction loss: How far did we get from the actual image?
            rec_loss = tf.reduce_sum(tf.square(y_padded - dec), axis=1)
            self.rec_loss = tf.reduce_mean(rec_loss)

            # 2. KL-Divergence: How far from the "true" distribution of z's is
            #                   our parameterised z?
            kl_loss = tf.reduce_sum( 0.5 * (tf.exp(log_sigma) + tf.square(mu) - 1. - log_sigma) , axis=1)
            self.kl_loss = tf.reduce_mean(kl_loss)
            self.loss = self.kl_loss + self.rec_loss
            
        self.saver = tf.train.Saver()

    def Train(self, train_gen, test_gen, save_dir, epochs=10, lr=0.001):

        assert_message = "Name must be unique, This will be the name of the dir we'll used to save checkpoints"
        assert not os.path.exists(save_dir), "{}: {}".format(assert_message, save_dir)
        os.makedirs(save_dir)

        optimizer = tf.train.AdamOptimizer(learning_rate=lr)
        train_step = optimizer.minimize(self.loss)

        self.train_loss = {"total": [], "kl": [], "rec": []}
        self.test_loss  = {"total": [], "kl": [], "rec": []}
        best_ckpt = ""
        with tf.Session() as sess:
            sess.run(tf.global_variables_initializer())
            best_loss = 10**9.0  # some big number


            for e in range(epochs):
                temp_train_loss = []
                train_gen.reset()
                t_train = trange(train_gen.steps_per_epoch)
                t_train.set_description(f"Training Epoch: {e+1}")
                for step in t_train:
                    images, annos = train_gen.get_next_batch()
                    _, loss, rec, kl = sess.run([train_step, self.loss, self.rec_loss, self.kl_loss],
                               feed_dict={self.x: images, self.y: annos, self.training: True})
                    temp_train_loss.append(np.array([loss, rec, kl]))
                
                means = np.mean(np.array(temp_train_loss), axis=0)
                self.train_loss["total"].append(means[0])
                self.train_loss["rec"].append( means[1])
                self.train_loss["kl"].append(  means[2])
                cur_loss = means[0]
                print(f"Train Loss: {cur_loss:0.3f}")
                
                test_gen.reset()
                temp_test_loss = []
                t_test = trange(test_gen.steps_per_epoch)
                t_test.set_description('Testing')
                for _ in t_test:
                    images, annos = test_gen.get_next_batch()
                    loss, rec, kl = sess.run([self.loss, self.rec_loss, self.kl_loss],
                           feed_dict={self.x: images, self.y: annos, self.training: False})
                    temp_test_loss.append(np.array([loss, rec, kl]))
                
                means = np.mean(np.array(temp_test_loss), axis=0)
                self.test_loss["total"].append(means[0])
                self.test_loss["rec"].append( means[1])
                self.test_loss["kl"].append(  means[2])                
                
                cur_loss = means[0]
                print(f"Test Loss: {cur_loss:0.3f}")
                print("-"*50)
                if cur_loss < best_loss:
                        best_loss = cur_loss
                        path = f"{save_dir}/ep_{e+1}_loss_{best_loss:0.3f}.ckpt"
                        best_ckpt = self.saver.save(sess, path)
                        print("Model saved at {}".format(best_ckpt))

        self.SaveLossPlots(save_dir)
        print(f"Done, final best loss: {best_loss:0.3f}")
        return best_ckpt

    def SaveLossPlots(self, save_dir):
        import matplotlib.pyplot as plt
        import json
        
        for loss_type in self.train_loss.keys():
            # print(f"Train: {self.train_loss}")
            # print(f"Test:  {self.test_loss}")
            fig = plt.figure(figsize=(8,6))
            plt.plot(self.train_loss[loss_type], 'b-',  label="train")
            plt.plot(self.test_loss[loss_type],  'r--', label="test")
            plt.title(f'{loss_type} loss during training')
            plt.xlabel("Loss")
            plt.ylabel("Epoch")
            plt.legend()
            path = os.path.join(save_dir, f"{loss_type}_training_loss.jpg")
            fig.savefig(path)
        
        # self.train_loss["total"] = [str(x) for x in self.train_loss["total"]]
        # self.train_loss["rec"] = [str(x) for x in self.train_loss["rec"]]
        # self.train_loss["kl"] = [str(x) for x in self.train_loss["kl"]]
        # self.test_loss["total"] = [str(x) for x in self.test_loss["total"]]
        # self.test_loss["rec"] = [str(x) for x in self.test_loss["rec"]]
        # self.test_loss["kl"] = [str(x) for x in self.test_loss["kl"]]
        
        self.train_loss["total"] = [float(x) for x in self.train_loss["total"]]
        self.train_loss["rec"] = [float(x) for x in self.train_loss["rec"]]
        self.train_loss["kl"] = [float(x) for x in self.train_loss["kl"]]
        self.test_loss["total"] = [float(x) for x in self.test_loss["total"]]
        self.test_loss["rec"] = [float(x) for x in self.test_loss["rec"]]
        self.test_loss["kl"] = [float(x) for x in self.test_loss["kl"]]
        
        with open(os.path.join(save_dir, "train.json"), 'w') as f:
            json.dump(self.train_loss, f)
        with open(os.path.join(save_dir, "test.json"), 'w') as f:
            json.dump(self.test_loss, f)
'''
    def Evaluate(self, eval_gen, checkpoint_path, save_figs=False, save_dir=None):
        pass
        
    def TrainingResults(self):
        pass
        #return self.train_loss, self.test_loss, self.test_acc

    def Predict(self, images, checkpoint_path):
        pass
        #with tf.Session() as sess:
        #    self.saver.restore(sess,checkpoint_path)
        #    return sess.run([self.steering_probs, self.expected_bin], feed_dict={self.x:images, self.training: False})

    def GetGraph(self):
        return tf.get_default_graph().as_graph_def()

'''