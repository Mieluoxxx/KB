import torch
import numpy as np
import torch.nn as nn
import math
import copy
import random
import matplotlib.pyplot as plt
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader


from GraphTransformerEncoder import *
from GraphTransformerDecoder import *
from RecognitionNetwork import *
from PriorNetwork import *


'''
This py part is aim to achieve the function of KG Graph Signal and Brain EEG Graph Signal Sychronization.
This function will return a latent variable A_L which describes the cause and effect relationship between  KG Graph Signal and 
 Brain EEG Graph Signal.
 
         
'''



class SYN(nn.Module):
    def __init__(self,input_dim,output_dim,dropout_rate,
                 KG_num,
                 embed_dim,
                 num_in_degree,
                 num_out_degree,
                 num_heads,
                 hidden_size,
                 ffn_size,
                 num_layer
                 ,num_decoder_layers,
                 attention_prob_dropout_prob,num_layers):
        super(SYN,self).__init__()
        self.DenseLayer = DenseLayer(input_dim,output_dim)
        self.FlattenLayer = FlattenLayer()
        self.encoder = GraphTransformerEncoder(dropout_rate,
                 KG_num,
                 embed_dim,
                 num_in_degree,
                 num_out_degree,
                 num_heads,
                 hidden_size,
                 ffn_size,
                 num_layer)
        self.decoder = GraphTransformerDecoder(hidden_size,dropout_rate,num_in_degree,embed_dim,num_out_degree,num_decoder_layers,num_heads,ffn_size)
        self.p_net = PriorNetwork(embed_dim,num_heads,input_dim,output_dim)
        self.q_net = RecognitionNetwork(num_layers,embed_dim,hidden_size,num_heads,attention_prob_dropout_prob,dropout_rate,input_dim,output_dim)
        self.self_att = nn.MultiheadAttention(embed_dim,num_heads)
        self.mult_att = nn.MultiheadAttention(embed_dim,num_heads)
        self.norm = LayerNorm(hidden_size)
        self.fn_fc = nn.Linear(embed_dim*KG_num,3)
        self.Sigmoid = torch.nn.Sigmoid()


    def forward(self,KG_embed_vector,BG_embed_vector,in_degree,out_degree):

        KG_hidden_state = self.encoder(KG_embed_vector,in_degree,out_degree)

        z_p = self.p_net(KG_hidden_state)
        z_q = self.q_net(KG_hidden_state,A)


        cov = torch.ones_like(z_p)
        p = torch.distributions.normal.Normal(z_p,cov)
        q = torch.distributions.normal.Normal(z_q,cov)

        A_L = torch.matmul(z_p,z_q)
        A_L = torch.softmax(A_L,dim=-1)
        print(A_L.shape)

        BG_hidden_state = torch.matmul(KG_hidden_state,A_L)
        BG_Graph_Construct = self.decoder(BG_hidden_state,in_degree,out_degree)
        BG_Graph_Construct = self.norm(BG_Graph_Construct)
        A_L = self.FlattenLayer(A_L)
        output = self.Sigmoid(self.fn_fc(A_L))
        output = self.fn_fc(A_L)
        print(output)


        return BG_Graph_Construct,p,q,output






class DenseLayer(nn.Module):
    def __init__(self,input_dim,output_dim):
        super(DenseLayer, self).__init__()
        self.fc = nn.Linear(input_dim,output_dim)

    def forward(self,x):
        output = self.fc(x)
        return output



class FlattenLayer(nn.Module):
    def __init__(self):
        super(FlattenLayer,self).__init__()

    def forward(self,x):
        return x.view(x.shape[0],-1)



class LayerNorm(nn.Module):
    def __init__(self, hidden_size, eps=1e-12):
            """Construct a layernorm module in the TF style (epsilon inside the square root).
            """
            super(LayerNorm, self).__init__()
            self.weight = nn.Parameter(torch.ones(hidden_size))
            self.bias = nn.Parameter(torch.zeros(hidden_size))
            self.variance_epsilon = eps

    def forward(self, x):
            u = x.mean(-1, keepdim=True)
            s = (x - u).pow(2).mean(-1, keepdim=True)
            x = (x - u) / torch.sqrt(s + self.variance_epsilon)
            return self.weight * x + self.bias



def train(model,train_dataloader,mae,critrion,device,train_epoch,batch_size,lr,scheduler_type='Cosine'):
    def init_xavier(m):
        if type(m) == nn.Linear:
            nn.init.kaiming_normal_(m.weight)#xavier_normal_

    model.apply(init_xavier)
    print(device)
    device = torch.device("cpu")
    optimizer = optim.Adam(model.parameters(),lr)
    #mae = loss1()
    #critirion = loss2()
    if scheduler_type == 'Cosine':
        scheduler = CosineAnnealingLR(optimizer,T_max=train_epoch)
        print ('using CosineAnnealingLR')
    train_loss = []
    train_loss1 = []
    train_loss2 = []
    train_loss_kl = []
    train_acces = []
    eval_acces = []
    best_acc = 0.0


    for epoch in range (train_epoch):
        model.train()
        train_acc = 0




        for batch_idx ,(KG_embed_vector,BG_embed_vector,in_degree,out_degree,labels) in enumerate(train_dataloader):
            BG_Graph_Construct,p,q,output = model(KG_embed_vector,BG_embed_vector,in_degree,out_degree)
            print(output.shape)
            print(labels.shape)
            #x = output.detach().numpy()
            #print(x.shape)
            #plt.imshow(x[0,0:62,:], cmap='jet', interpolation='nearest')
            #plt.colorbar()
            #plt.show()


            loss1 = mae(BG_embed_vector,BG_Graph_Construct)
            loss2 = critrion(output,labels)
            loss_kl = torch.distributions.kl.kl_divergence(p,q).sum()
            kl_lambda =0.0001
            loss = loss1 + loss2 + kl_lambda*loss_kl
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),max_norm=2)
            optimizer.step()

            _, pred = output.max(1)
            print(pred)
            print(labels)

            num_correct = (pred == labels).sum().item()
            print(num_correct)

            acc = num_correct / (batch_size)
            train_acc += acc


        scheduler.step()
        print("epoch: {}, Loss: {}, Acc: {}".format(epoch, loss.item(), train_acc / len(train_dataloader)))
        #print(len(train_dataloader))
        train_acces.append(train_acc / len(train_dataloader))
        train_loss.append(loss.item())
        train_loss1.append(loss1.item())
        train_loss2.append(loss2.item())
        train_loss_kl.append(loss_kl.item())


    return train_acces, train_loss, train_loss1, train_loss2,train_loss_kl






def showpic(train_acc, train_loss,train_loss1,train_loss2,train_loss_kl,num_epoch):
    plt.figure()
    plt.subplot(2,2,1)
    print(train_loss)
    plt.plot(1 + np.arange(len(train_loss)), train_loss, linewidth=1.5, linestyle='dashed', label='train_loss')
    plt.subplot(2,2,2)
    plt.plot(1 + np.arange(len(train_loss1)), train_loss1, linewidth=1.5, linestyle='dashed', label='train_loss1')
    plt.subplot(2,2,3)
    plt.plot(1 + np.arange(len(train_loss2)), train_loss2, linewidth=1.5, linestyle='dashed', label='train_loss2')
    plt.subplot(2,2,4)
    plt.plot(1 + np.arange(len(train_acc)), train_acc, linewidth=1.5, linestyle='dashed', label='train_acc')
    #plt.plot(1+np.arange(len(train_loss_kl)),train_loss_kl,linewidth=1.5,linestyle='dashed',label='train_loss_kl')
    plt.grid()
    plt.xlabel('epoch')
    plt.xticks(range(1, 1 + num_epoch,2))
    plt.legend()
    plt.show()
    #plt.plot(1+np.arange(len(eval_acces)),eval_acces,linewidth=1.5, linestyle='dashed', label='eval_acces')
    #plt.show()






'''
    debugging of SYN function .
    Input of this function contains:
     KG_embed_vector:(batch_size,KG_node_num,KG_embed_dim)
     In_degree:(batch_size,KG_node_num,1)
     Out_degree:(batch_size,KG_node_num,1)
     BG_embed_vector:(batch_size,BG_node_num,BG_embed_dim)
     
     
     Output of this function:
     BG_Graph_Construct: Use in loss 
     A_L: Sychronization between KG and BG
     p: learnt from KG_embed_vector in PriorNetwork  Use in KL Loss to minimize the distribution between p and q 
     q: learnt from BG_embed_vector in RecognitionNetwork  
'''
     

if __name__ == '__main__':
    #random.seed(100)
    KG_input_dim =128
    KG_output_dim =128
    dropout_rate =0.1
    KG_num = 128
    embed_dim = 128
    num_in_degree =128
    num_out_degree =128
    num_heads = 8
    hidden_size =128
    ffn_size =128
    num_decoder_layers = 3
    attention_prob_dropout_prob =0.1
    num_layers = 3


    KG_embed_vector = torch.randn(100,128,128)
    in_degree = torch.randint(0,5,(100,128))
    out_degree = torch.randint(0,5,(100,128))
    BG_embed_vector = torch.randn(100,128,128)
    #print(BG_embed_vector.shape)
    label_part = np.array([2,0,2,2])
    labels = np.tile(label_part,25)
    labels = torch.LongTensor(labels)
    device = torch.device('cpu')

    train_data = torch.utils.data.TensorDataset(KG_embed_vector,BG_embed_vector,in_degree,out_degree,labels)
    train_dataloader = torch.utils.data.DataLoader(train_data,batch_size=4,shuffle=False, drop_last=False)
    model = SYN(input_dim,output_dim,dropout_rate,
                 KG_num,
                 embed_dim,
                 num_in_degree,
                 num_out_degree,
                 num_heads,
                 hidden_size,
                 ffn_size,
                 num_layers
                 ,num_decoder_layers,
                 attention_prob_dropout_prob,num_layers)
    mae = nn.L1Loss()
    critrion = nn.CrossEntropyLoss()
    #CrossEntropyLoss = nn.CrossEntropyLoss()

    train_acces, train_loss, train_loss1, train_loss2,train_loss_kl = train(model,train_dataloader,mae,critrion,device,batch_size=4,train_epoch=20,lr=1e-5)
    #print(len(train_acces))
    #print(len(train_loss))
    showpic(train_acces, train_loss,train_loss1,train_loss2,train_loss_kl,num_epoch=20)
#    for name, parms in model.named_parameters():
#        print(name)
#        print(parms.requires_grad)
#        print(parms.grad)


