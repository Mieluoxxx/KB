import torch
import torch.nn as nn
import math
from torch.nn import MultiheadAttention



'''
 This part of PriorNetwork aim to learn and model the representation of p(z|x)
At First ,the representation of KG transfer by Graph TransformerEncoder will be passed to the attention mechanism  to 
promote the fusion of the graph contextual information and relational information ,and then be passed to the Dense Layers   
to extract the hidden representation features by nonlinear changes in the Dense Layers and finally map out it into the output 
space  and model the distribution based on the input KG transformation
  
'''



class PriorNetwork(nn.Module):
    def __init__(self,embed_dim,num_heads,input_dim,output_dim):
        super(PriorNetwork,self).__init__()
        self.attentionLayer = AttentionLayer(embed_dim,num_heads)
        self.Dense = DenseLayer(input_dim,output_dim)


    def forward(self,KG_embed_vector):
        KG_update_vector ,KG_attn= self.attentionLayer(KG_embed_vector)
        #print(KG_update_vector.shape)
        KG_update_vector = self.Dense(KG_update_vector)
        z,attn_score = self.attentionLayer(KG_update_vector)

        return z






class AttentionLayer(nn.Module):
    def __init__(self,embed_dim,num_heads):
        super( AttentionLayer, self ).__init__()
        self.attention = nn.MultiheadAttention(embed_dim,num_heads)

    def forward(self,hidden_state):
        attn,context_vector = self.attention(query=hidden_state,key=hidden_state,value=hidden_state)
        return attn,context_vector







class DenseLayer(nn.Module):
    def __init__(self,input_dim,output_dim):
        super(DenseLayer, self).__init__()
        self.fc = nn.Linear(input_dim,output_dim)

    def forward(self,x):
        output = self.fc(x)
        return output




class MultiAttention(nn.Module):
    def __init__(self, hidden_size, attention_dropout_rate, num_heads):
        super(MultiAttention, self).__init__()

        self.num_heads = num_heads
        self.attention_size = hidden_size // num_heads
        self.scale = self.attention_size ** -0.5

        self.query_layer = nn.Linear(hidden_size, num_heads * self.attention_size)
        self.key_layer = nn.Linear(hidden_size, num_heads * self.attention_size)
        self.value_layer = nn.Linear(hidden_size, num_heads * self.attention_size)

        self.dropout_layer = nn.Dropout(attention_dropout_rate)
        self.ouput_layer = nn.Linear(num_heads * self.attention_size, hidden_size)

    def forward(self, q, k, v, attention_bias=None):
        orig_q_size = q.size()

        d_k = self.attention_size
        d_v = self.attention_size
        batch_size = q.size(0)

        q = self.query_layer(q).view(batch_size, 1, self.num_heads, d_k)
        k = self.key_layer(k).view(batch_size, 1, self.num_heads, d_k)
        v = self.value_layer(v).view(batch_size, 1, self.num_heads, d_v)

        q = q.transpose(1, 2)
        k = k.transpose(1, 2).transpose(2, 3)
        v = v.transpose(1, 2)

        # Attention_score computing
        q = q * self.scale
        x = torch.matmul(q, k)
        if attention_bias is not None:
            x = x + attention_bias
        x = torch.softmax(x, dim=3)
        x = self.dropout_layer()
        x = x.matmul(v)

        x = x.transpose(1, 2).contiguous()
        x = x.view(batch_size, -1, self.num_heads * d_v)
        x = self.ouput_layer(x)
        assert x == orig_q_size
        return x



#KG_embed_vector = torch.randn(1,128,128)

#embed_dim = 128
#num_heads = 8
#input_dim = 128
#output_dim = 128
#model = PriorNetwork(embed_dim, num_heads, input_dim, output_dim)
#z = model(KG_embed_vector)
#print(z[0].shape)
