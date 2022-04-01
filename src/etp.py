import bottleneck as bn
from datetime import datetime
from dfg import check_dfg_compliance
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import pprint
import pathlib
from sklearn.metrics import precision_recall_fscore_support
import torch                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm
from utils import get_available_actions
from statistics import mean
import csv

np.set_printoptions(linewidth=1000)


device=torch.device('cuda:0')
plt.style.use('ggplot')



# Define an RNN model (The generator)
class LSTMGenerator(nn.Module):
    def __init__(self, seq_len, input_size, batch, hidden_size, num_layers, num_directions):
        super().__init__()
        print("lstm params:",seq_len, input_size, batch, hidden_size, num_layers, num_directions)
        self.input_size = input_size
        self.h = torch.randn(num_layers * num_directions, batch, hidden_size)
        self.c = torch.randn(num_layers * num_directions, batch, hidden_size)

        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, dropout=0.25, batch_first=True, bidirectional=False)
        # h0 = torch.randn(,1, 513)
        # c0 = torch.randn(1,1, 513)

        latent_vector_size = 50 * batch
        self.linear1 = nn.Linear(batch * seq_len * hidden_size, latent_vector_size)
        # self.linear2 = nn.Linear(latent_vector_size,batch*seq_len*hidden_size)
        self.linearHC = nn.Linear(num_layers * hidden_size * batch, latent_vector_size)
        # self.linearHCO = nn.Linear(3*latent_vector_size,batch*seq_len*hidden_size )
        self.linearHCO = nn.Linear(3 * latent_vector_size, batch * seq_len * input_size)

        # h0.data *=0.001
        # c0.data *=0.001

        # Define sigmoid activation and softmax output
        self.relu = nn.ReLU()
        self.softmax = nn.Softmax()

    def forward(self, x):
        # x = x.view((1,x.size()[0], x.size()[1]))
        # Pass the input tensor through each of our operations
        # print("inputsize:", x.size())
        output, (h, c) = self.lstm(x, (self.h, self.c))
        # print("inputsize:", x.size(),"output size:", output.size())
        # print("h size:", h.size(),"c size:", c.size())
        self.h = h.detach()
        self.c = c.detach()

        # Executing Fully connected network
        # print("The size of output:", output.size(), h.size(), c.size())
        u = output.reshape((output.size()[0] * output.size()[1] * output.size()[2]))
        u = self.relu(self.linear1(u))
        # print("The size of lninera1:", u.size())
        # u = self.linear2(u)

        # Flating h and feeding it into a linear layer
        uH = F.leaky_relu(self.linearHC(h.reshape((h.size()[0] * h.size()[1] * h.size()[2]))))
        uC = F.leaky_relu(self.linearHC(c.reshape((c.size()[0] * c.size()[1] * c.size()[2]))))
        uHCO = torch.cat((uH, uC, u))
        uHCO = self.linearHCO(uHCO)
        u = uHCO
        # print("u",u)
        output = u.view((output.size()[0], output.size()[1], self.input_size))
        # print("output",output)
        # For the time stamp it the dimension of the output is 1
        # output = u.view((output.size()[0],output.size()[1],1))
        # print("output size finally:", output.size())

        return output

####################################################################################################
#Defining the discriminator
class LSTMDiscriminator(nn.Module):
    def __init__(self, seq_len, input_size, batch, hidden_size, num_layers, num_directions):
        super().__init__()
        self.batch = batch
        self.h = torch.randn(num_layers * num_directions, batch, hidden_size)
        self.c = torch.randn(num_layers * num_directions, batch, hidden_size)

        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, dropout=0.25, batch_first=True, bidirectional=False)
        # h0 = torch.randn(,1, 513)
        # c0 = torch.randn(1,1, 513)

        latent_vector_size = 50 * batch
        self.linear1 = nn.Linear(batch * seq_len * hidden_size, latent_vector_size)
        self.linearHC = nn.Linear(num_layers * hidden_size * batch, latent_vector_size)
        # self.linearHCO = nn.Linear(3*latent_vector_size,batch*seq_len*input_size )
        self.linearHCO = nn.Linear(3 * latent_vector_size, batch * seq_len * input_size)
        self.linear2 = nn.Linear(batch * seq_len * input_size, 100)
        self.linear3 = nn.Linear(100, 50)
        self.linear4 = nn.Linear(50, batch)

        # h0.data *=0.001
        # c0.data *=0.001

        # Define sigmoid activation and softmax output
        self.relu = nn.ReLU()
        self.softmax = nn.Softmax()

    def forward(self, x):
        # x = x.view((1,x.size()[0], x.size()[1]))
        # Pass the input tensor through each of our operations
        output, (h, c) = self.lstm(x, (self.h, self.c))
        # print("inputsize:", x.size(),"output size:", output.size())
        self.h = h.detach()
        self.c = c.detach()

        # Executing Fully connected network
        # print("The size of output:", output.size(), h.size(), c.size())
        u = output.reshape((output.size()[0] * output.size()[1] * output.size()[2]))
        u = self.relu(self.linear1(u))
        # u = self.linear2(u)

        # Flating h and feeding it into a linear layer
        uH = F.leaky_relu(self.linearHC(h.reshape((h.size()[0] * h.size()[1] * h.size()[2]))))
        uC = F.leaky_relu(self.linearHC(c.reshape((c.size()[0] * c.size()[1] * c.size()[2]))))
        uHCO = torch.cat((uH, uC, u))
        uHCO = self.linearHCO(uHCO)
        u = F.relu(self.linear2(uHCO))
        u = F.relu(self.linear3(u))
        u = self.linear4(u)

        # output = u.view((output.size()[0],output.size()[1],output.size()[2]))
        # output = u.view((output.size()[0],output.size()[1],input_size))
        output = u

        # Reshaping into (batch,-1)
        # tensor([[-0.1050],
        # [ 0.0327],
        # [-0.0260],
        # [-0.1059],
        # [-0.1055]], grad_fn=<ViewBackward>)
        output = output.reshape((self.batch, -1))

        return output
####################################################################################################
def one_hot_encoding(batch, no_events, y_truth):
    '''
    batch : the batch size
    no_events : the number of events
    y_truth : the ground truth labels

    example:
      tensor([[8.],
        [6.],
        [0.],
        [0.],
        [8.]])

    tensor([[0., 0., 0., 0., 0., 0., 0., 0., 1., 0.],
        [0., 0., 0., 0., 0., 0., 1., 0., 0., 0.],
        [1., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
        [1., 0., 0., 0., 0., 0., 0., 0., 0., 0.],
        [0., 0., 0., 0., 0., 0., 0., 0., 1., 0.]])'''

    z = torch.zeros((batch, no_events))
    for i in range(z.size()[0]):
        z[i, y_truth[i].long()] = 1

    # print(z)
    return z.view(batch, 1, -1)
###################################################################################################
def grad_regularization(model, sd = 0.0075 ):
  '''
  This method add random numbers from a white noise to the gradients of LSTM at each layer to avoid vanishing of that
  @param model: A neural network object, such as LSTM, or MLP
  @param sd: standard deviation
  @return: Update the gradient of each layer
  '''
  #Regularizing the gradients of LSTM by adding random numbers from a white guassian
  m = torch.distributions.normal.Normal(0, scale = sd, validate_args=None)
  for p in model.named_parameters():
    if('lstm' in p[0]):
        p[1].grad+= m.sample(sample_shape=p[1].grad.size())
###################################################################################################
def get_seq_and_duration(df,caseid_lis, adr):
    seq = []
    dur_time_cp = []
    caseid_lis = np.unique(caseid_lis)
    for caseid in caseid_lis:
        temp_df = df[df['CaseID'] == caseid].sort_values(by="CompleteTimestamp")
        temp_df = temp_df[['ActivityID', 'duration_time', 'remaining_time']].to_numpy()
        i = 0
        indices = np.where(np.isclose(temp_df, adr[0]).all(axis = 1))[0]
        if(len(indices)!=0):
            for i in range(1, len(adr)):
                temp_indices = indices + i
                if len(temp_indices):
                    if(max(temp_indices)< len(temp_df)):
                        temp_df2 = temp_df[temp_indices]
                        temp_indices_2 = np.where(np.isclose(temp_df2, adr[i]).all(axis = 1))[0]
                        indices = indices[temp_indices_2]
            try:
                indices = np.arange(indices[0])
                seq.append([temp_df[indices].T[0].astype(int)])
                dur_time_cp.append(temp_df[indices].T[0])
            except Exception as e: print(e)
            
            
    return seq, dur_time_cp

def model_eval_test(modelG, mode, obj,csvwriter,calledbyTrain = False,epoch = 0):
    '''
       This module is for validation and testing the Generator
       @param modelG: Generator neural network
       @param mode: 'validation', 'test', 'test-validation'
       @param obj: A data object created from "Input" class that contains the required information
       @return: The accuracy of the Generator
       '''
    # set the evaluation mode (this mode is necessary if you train with batch, since in test the size of batch is different)
    rnnG = modelG
    rnnG.eval()

    validation_loader = obj.validation_loader
    test_loader = obj.test_loader
    batch = obj.batch
    #events = list(np.arange(0, len(obj.unique_event) + 1))
    events = list(np.arange(0, len(obj.unique_event)))
    prefix_len = obj.prefix_len
    selected_columns = obj.selected_columns
    timestamp_loc = obj.timestamp_loc


    if (mode == 'validation'):
        data_loader = validation_loader
    elif (mode == "test"):
        data_loader = test_loader
    elif (mode == 'test-validation'):
        data_loader = test_loader + validation_loader

    predicted = []
    accuracy_record = []
    accuracy_time_stamp = []
    accuracy_time_stamp_per_event = {}
    accuracy_pred_per_event = {}
    mistakes = {}
    dfg_compliance_pred = []
    dfg_compliance_gt = []
    accuracy_record_2most_probable = []
    y_truth_list = []
    y_pred_last_event_list = []
    df = pd.read_pickle("dataset/preprocessed/"+obj.dataset_name+".pkl")
    dur = 0
    dur_gt = 0
    num_overall_goal_satisfied = 0
    num_overall_goal_not_satisfied = 0
    num_overall_goal_satisfied_gt = 0
    num_overall_goal_not_satisfied_gt = 0
    row = []

    for mini_batch in iter(data_loader):
        x = mini_batch[0];
        y_truth = mini_batch[1]
        activites = torch.argmax(x[:, :, events])
        # print("y_truth\n",y_truth)
        # When we create mini batches, the length of the last one probably is less than the batch size, and it makes problem for the LSTM, therefore we skip it.
        if (x.size()[0] < batch):
            continue
        # print("x.size()", x.size())

        # Separating event and timestamp
        y_truth_timestamp = y_truth[:, :, 0].view(batch, 1, -1)
        y_truth_event = y_truth[:, :, 1].view(batch, 1, -1)
        # Executing LSTM
        y_pred = rnnG(x[:, :, selected_columns])

        # Just taking the last predicted element from each the batch
        y_pred_last = y_pred[0: batch, prefix_len - 1, :]
        y_pred_last = y_pred_last.view((batch, 1, -1))

        y_pred_last_event = torch.argmax(F.softmax(y_pred_last[:, :, events], dim=2), dim=2)
        
        #Storing list of predictions and corresponding ground truths (to be used for f1score)
        y_truth_list += list(y_truth_event.flatten().data.cpu().numpy().astype(int))
        y_pred_last_event_list += list(y_pred_last_event.flatten().data.cpu().numpy().astype(int))

        y_pred_second_last = y_pred[0: batch, prefix_len - 2, :]
        y_pred_second_last = y_pred_second_last.view((batch, 1, -1))
        y_pred_second_last_event = torch.argmax(F.softmax(y_pred_second_last[:, :, events], dim=2), dim=2)
        
        
        cur_act_seq = torch.argmax(x.detach()[:, :, events], dim=2)
        
        # print("cur_act_seq",cur_act_seq)
        # find acitivies that occured before cur_act_seq in the process
        le = len(obj.unique_event)+3
        caseid_lis = x.detach()[:, :, le]
        caseid_lis = np.array(caseid_lis).astype(int)[0]
        cur_case_id = caseid_lis[0]
        dur_time_lis = np.array(x.detach()[:, :, len(events):len(events)+1][0]).T[0].astype(np.float64)
        rem_time_lis = np.array(x.detach()[:, :, len(events)+1:len(events)+2][0]).T[0].astype(np.float64)
        adr = np.vstack((cur_act_seq ,dur_time_lis,rem_time_lis)).T
        seq, dur_t = get_seq_and_duration(df,caseid_lis, adr) #list of sequences
        
        val = np.sum(np.array(dur_t[:obj.prefix_len]))
        # print("dur {} val {} vel len{}".format(dur,val,len(np.array(dur_t[:obj.prefix_len]))))
        
        dur += val # time from prefix start to cur prefix length
        dur_gt += val
        if(len(seq)!=0):
            cur_act_seq = np.append(seq[0],cur_act_seq)

        # checking dfg compliance for predicted event
        dfg_compliance_bool = check_dfg_compliance(cur_act_seq[-1], y_pred_last_event.detach(), dset=obj.dataset_name)
        dfg_compliance_pred.append(int(dfg_compliance_bool))
        
        # # checking dfg compliance for ground-truth
        dfg_compliance_gt_bool = check_dfg_compliance(cur_act_seq[-1], y_truth_event.detach().reshape(y_pred_last_event.shape), dset=obj.dataset_name)
        dfg_compliance_gt.append(int(dfg_compliance_gt_bool))


        # Computing MAE for the timestamp
        y_pred_timestamp = y_pred_last[:, :, timestamp_loc].view((batch, 1, -1))
        accuracy_time_stamp.append(torch.abs(y_truth_timestamp - y_pred_timestamp).mean().detach())
        # print("y_pred_timestamp",y_pred_timestamp)

        dur += min(y_pred_timestamp.detach().numpy()[0][0],0)  #adding to total proccess duration, making sure y_pred is non-negative
        dur_gt += min(y_truth_timestamp.detach().numpy()[0][0],0)

        thresh = 13.89
        if obj.dataset_name == "helpdesk":
            thresh = 13.89 
        if obj.dataset_name == "bpi_12_w":
            thresh = 18.28
        if obj.dataset_name == "traffic_ss":
            thresh = 607.04
        
        # # GS cases
        if int(y_truth_event.detach().numpy()[0][0]) == 0: # end of trace 
            ca = cur_act_seq[-1]
            
            try:
                if  ca != 0:   #avoding zero loop
                    if dur < thresh:
                        num_overall_goal_satisfied += 1
                        
                        # gs_pred_cases.append(caseid_lis[self.cur_case_idx])
                    else:
                        num_overall_goal_not_satisfied += 1
                    
                    if dur_gt < thresh:
                        num_overall_goal_satisfied_gt += 1
                        
                        # gs_pred_cases.append(caseid_lis[self.cur_case_idx])
                    else:
                        num_overall_goal_not_satisfied_gt += 1
            
                        # gv_pred_cases.append(caseid_lis[self.cur_case_idx])
            except Exception as e: print(e)
            dur = 0
            

                
        # compliant = 0
        #Iterating over the minibatch
        for i in range(x.size()[0]):
        #     possible_actions = get_available_actions(y_truth_event[i], obj.env_name) 
          
        #     if y_pred_last_event[i] in possible_actions:
        #         compliant += 1

            if (y_pred_last_event[i] == y_truth_event[i].long()):
                correct_prediction = 1
            else:
                correct_prediction = 0

                # Collecting the mistakes
                k = str(y_truth_event[i].detach()) + ":" + str(y_pred_last_event[i].detach()) + str(
                    y_pred_second_last_event[i].detach())
                if (k not in mistakes):
                    mistakes[k] = 1
                else:
                    mistakes[k] += 1

            # Considering the second most probable
            if ((y_pred_second_last_event[i] == y_truth_event[i].long()) or (
                    y_pred_last_event[i] == y_truth_event[i].long())):
                correct_prediction_2most_probable = 1
            else:
                correct_prediction_2most_probable = 0

            # accuracy_record.append(correct_prediction/float(len(y_pred)))
            accuracy_record.append(correct_prediction)
            accuracy_record_2most_probable.append(correct_prediction_2most_probable)
            predicted.append(y_pred)

            # Computing accuracy per event

            if str(y_truth_event[i]) in accuracy_pred_per_event:
                accuracy_pred_per_event[str(y_truth_event[i])].append(correct_prediction)
            else:
                accuracy_pred_per_event[str(y_truth_event[i])] = [(correct_prediction)]

            # Computing MAE per events
            if str(y_truth_event[i]) in accuracy_time_stamp_per_event:
                accuracy_time_stamp_per_event[str(y_truth_event[i].detach())].append(
                    torch.abs(y_truth_timestamp[i] - y_pred_timestamp[i]).mean().detach())
            else:
                accuracy_time_stamp_per_event[str(y_truth_event[i].detach())] = [
                    torch.abs(y_truth_timestamp[i] - y_pred_timestamp[i]).mean().detach()]


        # # Computing MAE for the timestamp
        # y_pred_timestamp = y_pred_last[:, :, timestamp_loc].view((batch, 1, -1))
        # accuracy_time_stamp.append(torch.abs(y_truth_timestamp - y_pred_timestamp).mean().detach())

    rnnG.train()


    # computing F1scores wiethed
    weighted_precision, weighted_recall, weighted_f1score, support = precision_recall_fscore_support(y_truth_list,
                                                                                            y_pred_last_event_list,
                                                                                            average='weighted',
                                                                                            labels=events)
    # computing F1score per each label
    precision, recall, f1score, support = precision_recall_fscore_support(y_truth_list, y_pred_last_event_list, average=None, labels=events)

    #Calculating the mean accuracy of prediction per events
    for k in accuracy_pred_per_event.keys():
        accuracy_pred_per_event[k] = [np.mean(accuracy_pred_per_event[k]), len(accuracy_pred_per_event[k])]

    #Calculating the MAE(day) for timestamp prediction per events
    for k in accuracy_time_stamp_per_event.keys():
        accuracy_time_stamp_per_event[k] = [np.mean(accuracy_time_stamp_per_event[k]),len(accuracy_time_stamp_per_event[k])]

    if (mode == 'test'):
        
        #pprint.pprint(mistakes)
        if(os.path.isfile(obj.path+'/results.txt')):
            with open(obj.path+'/results.txt', "a") as fout:
                pprint.pprint(mistakes, stream=fout)
        else:
            with open(obj.path+'/results.txt', "w") as fout:
                pprint.pprint(mistakes, stream=fout)

        with open(obj.path + '/results.txt', "a") as fout:
            fout.write( "\n Turth: first prediction, second prediction\n" +
                       "total number of predictions:"+ str(len(accuracy_record))+','+str(np.sum(accuracy_record)) +
                       "\n The accuracy of the model with the most probable event:" + str(np.mean(accuracy_record))+
                       "\n The accuracy of the model with the 2 most probable events:" +str(np.mean(accuracy_record_2most_probable))+
                       '\n The MAE (days) for the next event prediction is:' + str(np.mean(accuracy_time_stamp)) +
                       '\n The list of activity names:' + str(events) +
                       '\n The precision per activity names:' + str(precision) +
                       '\n The recall per activity names:' + str(recall) +
                       '\n The F1 score per activity names:' + str(f1score) +
                       '\n The support per activity names:' + str(support) +
                       '\n The weighted precision, recall, and F1-score are: ' + str(weighted_precision)+','+str(weighted_recall)+','+str(weighted_f1score) +'\n' )

            fout.write("The recall of prediction per events (event, accuracy, frequency):\n")
            pprint.pprint(accuracy_pred_per_event, stream=fout)
            fout.write('The accuracy of timestamp prediction MAE(day) (event, MAE, frequency):\n')
            pprint.pprint(accuracy_time_stamp_per_event, stream=fout)
            fout.write("-----------------------------------------------------------------------\n")


        #fout.close()
    percent_overall_gs = 0
    percent_overall_gv = 0
    try:
        percent_overall_gs = num_overall_goal_satisfied/(num_overall_goal_satisfied+num_overall_goal_not_satisfied)
        percent_overall_gv = num_overall_goal_not_satisfied/(num_overall_goal_satisfied+num_overall_goal_not_satisfied)
    except:
        percent_overall_gs = 0
        percent_overall_gv = 0

    percent_overall_gs_gt = 0
    percent_overall_gv_gt = 0
    try:
        percent_overall_gs_gt = num_overall_goal_satisfied_gt/(num_overall_goal_satisfied_gt+num_overall_goal_not_satisfied_gt)
        percent_overall_gv_gt = num_overall_goal_not_satisfied_gt/(num_overall_goal_satisfied_gt+num_overall_goal_not_satisfied_gt)
    except:
        percent_overall_gs_gt = 0
        percent_overall_gv_gt = 0
    print("Labels:", events)
    print("Wighted Precision:", weighted_precision)
    print("Wighted Recall:", weighted_recall)
    print("Wighted F1score:", weighted_f1score)
    print("---------------------")
    print("Labels:", events)
    print("Precision:", precision)
    print("Recall:", recall)
    print("F1score:", f1score)
    print("Support:", support)


    dfg_gt = np.mean(dfg_compliance_gt)
    dfg_p = np.mean(dfg_compliance_pred)
    print("DFG graph compliance(compliance with process flow) of grount truth prfixes:" + str(dfg_gt))
    print("DFG graph compliance(compliance with process flow) of most probable event prediction:" + str(dfg_p))
    print("percent overall goal satisfied in preds: ",percent_overall_gs*100)
    print("percent overall goal not satisfied in preds ",percent_overall_gv*100)
    print("Truth: first prediction, second prediction\n")
    print("total number of predictions:", len(accuracy_record), np.sum(accuracy_record))
    acc = np.mean(accuracy_record)
    print("The accuracy of the model with the most probable event:", acc)
    print("The accuracy of the model with the 2 most probable events:", np.mean(accuracy_record_2most_probable))
    mae = np.mean(accuracy_time_stamp)
    print("The MAE value is:", mae)
    if calledbyTrain==False:
        row.append([obj.prefix_len, dfg_gt, dfg_p, percent_overall_gs, percent_overall_gv,percent_overall_gs_gt,percent_overall_gv_gt, acc, mae ])
    else:
        row.append([obj.prefix_len, epoch, dfg_gt, dfg_p, percent_overall_gs, percent_overall_gv, percent_overall_gs_gt,percent_overall_gv_gt,acc, mae ])
        
    csvwriter.writerows(row)



    return np.mean(accuracy_record)


###################################################################################################
def train(rnnG, rnnD, optimizerD, optimizerG, obj, epoch):
    '''
        @param rnnG: Generator neural network
        @param rnnD: Discriminator neural network
        @param optimizerD:  Optimizer of the discriminator
        @param optimizerG:  Optimizer of the generator
        @param obj:       A data object created from "Input" class that contains the training,test, and validation datasets and other required information
        @param epoch:    The number of epochs
        @return: Generator and Discriminator
    '''

    unique_event = obj.unique_event
    train_loader = obj.train_loader
    batch = obj.batch
    selected_columns = obj.selected_columns
    prefix_len = obj.prefix_len
    timestamp_loc = obj.timestamp_loc



    # Training Generator
    #epoch = 30
    events = list(np.arange(0, len(unique_event)))
    #events = list(np.arange(0, len(selected_columns)))
    gen_loss_pred = []
    disc_loss_tot = []
    gen_loss_tot = []
    dfg_compliance_pred = []
    dfg_compliance_gt = []
    accuracy_best = 0
    df = pd.read_pickle("dataset/preprocessed/"+obj.dataset_name+".pkl")
    for i in tqdm(range(epoch)):
        for mini_batch in iter(train_loader):
            log_path = obj.dataset_name+"log_train.csv"
            csvfile = open(log_path, 'w') 
            # creating a csv writer object
            csvwriter = csv.writer(csvfile)
            fields = ["prefix","epoch","dfg_gt","dfg_pred","percent_overall_gs","percent_overall_gv","accuracy","mae"]
            # writing the fields
            csvwriter.writerow(fields)

            x = mini_batch[0];
            y_truth = mini_batch[1]

            # When we create mini batches, the length of the last one probably is less than the batch size, and it makes problem for the LSTM, therefore we skip it.
            if (x.size()[0] < batch):
                continue
            # print('inputs: \n',x[:,:,selected_columns], x[:,:,selected_columns].size(),'\n y_truth:\n', y_truth)
            # print("Duration time input:\n", x[:,:, duration_time_loc].view((batch,-1,1)))
            # -----------------------------------------------------------------------------------------------------

            y_truth_timestamp = y_truth[:, :, 0].view(batch, 1, -1)
            y_truth_event = y_truth[:, :, 1].view(batch, 1, -1)

            # Training discriminator
            optimizerD.zero_grad()

            # Executing LSTM
            y_pred = rnnG(x[:, :, selected_columns])

            # Just taking the last predicted element from each the batch
            y_pred_last = y_pred[0:batch, prefix_len - 1, :]
            y_pred_last = y_pred_last.view((batch, 1, -1))
            
            
            # Converting the labels into one hot encoding
            y_truth_one_hot = one_hot_encoding(batch, len(events), y_truth_event)

            # Creating synthetic and realistic datasets
            ##data_synthetic = torch.cat((x[:,:,events],F.softmax(y_pred_last[:,:,events],dim=2)), dim=1)
            y_pred_last_event = torch.argmax(F.softmax(y_pred_last[:, :, events], dim=2), dim=2)
            y_pred_one_hot = one_hot_encoding(batch, len(events), y_pred_last_event)

            # cur_act_seq = torch.argmax(x.detach()[:, :, events], dim=2)
            
            # # find acitivies that occured before cur_act_seq in the process
            # le = len(obj.unique_event)+3
            # caseid_lis = x.detach()[:, :, le]
            # caseid_lis = np.array(caseid_lis).astype(int)[0]
            # dur_time_lis = np.array(x.detach()[:, :, len(events):len(events)+1][0]).T[0].astype(np.float64)
            # rem_time_lis = np.array(x.detach()[:, :, len(events)+1:len(events)+2][0]).T[0].astype(np.float64)
            # adr = np.vstack((cur_act_seq ,dur_time_lis,rem_time_lis)).T
            # seq, dur_t  = get_seq_and_duration(df,caseid_lis, adr) #list of sequences

            # if(len(seq)!=0):
            #     cur_act_seq = np.append(seq[0],cur_act_seq)
            
            # # checking dfg compliance for predicted event
            # # print("prev_act {} pred {}".format(cur_act_seq[-1], y_pred_last_event.detach()))
            # dfg_compliance_bool = check_dfg_compliance(cur_act_seq[-1], y_pred_last_event.detach(), dset=obj.dataset_name)
            # dfg_compliance_pred.append(int(dfg_compliance_bool))
            
            # # checking dfg compliance for ground-truth
            # dfg_compliance_gt_bool = check_dfg_compliance(cur_act_seq[-1], y_truth_event.detach().reshape(y_pred_last_event.shape), dset=obj.dataset_name)
            # dfg_compliance_gt.append(int(dfg_compliance_gt_bool))
        

            y_pred_timestamp = y_pred_last[:, :, timestamp_loc].view((batch, 1, -1))
            y_pred_one_hot_and_timestamp_last = torch.cat((y_pred_one_hot, y_pred_timestamp), dim=2)
            data_synthetic = torch.cat((x[:, :, selected_columns], y_pred_one_hot_and_timestamp_last), dim=1)


            # Realistinc dataset
            # Mixing the event and timestamp of the gound truth
            y_truth_one_hot_and_timestamp = torch.cat((y_truth_one_hot, y_truth_timestamp), dim=2)
            data_realistic = torch.cat((x[:, :, selected_columns], y_truth_one_hot_and_timestamp), dim=1)

            # Training Discriminator on realistic dataset
            discriminator_realistic_pred = rnnD(data_realistic)
            disc_loss_realistic = F.binary_cross_entropy(torch.sigmoid(discriminator_realistic_pred),
                                                         torch.ones((batch, 1)), reduction='sum')
            disc_loss_realistic.backward(retain_graph=True)

            # Gradient regularization
            ##grad_regularization(rnnD)

            # Training Discriminator on synthetic dataset
            discriminator_synthetic_pred = rnnD(data_synthetic)
            disc_loss_synthetic = F.binary_cross_entropy(torch.sigmoid(discriminator_synthetic_pred),
                                                         torch.zeros((batch, 1)), reduction='sum')
            disc_loss_synthetic.backward(retain_graph=True)

            # Gradient regularization
            ##grad_regularization(rnnD)

            disc_loss_tot.append(disc_loss_realistic.detach() + disc_loss_synthetic.detach())

            optimizerD.step()

            if len(disc_loss_tot) % 1000 == 0:
                print("iter =------------------------------ i :", i, len(disc_loss_tot), " the Disc error is:",
                      ", the avg is:", np.mean(disc_loss_tot))

            # -------------------------------------------------------------------------------------------------------------------------

            # Training teh Generator

            # Training the prediction for the generator

            optimizerG.zero_grad()

            # Computing the loss of prediction for events
            lstm_loss_pred = F.binary_cross_entropy(torch.sigmoid(y_pred_last[:, :, events]), y_truth_one_hot,
                                                    reduction='sum')
            # dfg_loss_wt = 100
            # dfg_compliance_loss = dfg_loss_wt*(int(dfg_compliance_gt_bool) - int(dfg_compliance_bool))
            
            # Computing the loss of timestamp
            lstm_loss_pred += F.mse_loss(y_pred_timestamp, y_truth_timestamp , reduction='sum')
            gen_loss_pred.append(lstm_loss_pred.detach())
            lstm_loss_pred.backward(retain_graph=True)

            # Gradient regularization
            ##grad_regularization(rnnG)

            # Fooling the discriminator by presenting the synthetic dataset and considering the labels as the real ones
            discriminator_synthetic_pred = rnnD(data_synthetic)
            gen_fool_dic_loss = F.binary_cross_entropy(F.sigmoid(discriminator_synthetic_pred), torch.ones((batch, 1)),
                                                       reduction='sum')
            gen_fool_dic_loss.backward(retain_graph=True)

            # Gradient regularization
            ##grad_regularization(rnnG)
            
            gen_loss_tot.append(lstm_loss_pred.detach() + gen_fool_dic_loss.detach())

            optimizerG.step()

            if len(gen_loss_tot) % 1000 == 0:
                print("iter =------------------------------ i :", i, len(gen_loss_tot), " the Gen error is:",
                      ", the avg is:", np.mean(gen_loss_tot))

        # Applying validation after several epoches
        # Early stopping (checking for every 5 iterations)
        path = obj.path
        # obj.path=path
        if i % 5 == 0:
            rnnG.eval()
            accuracy = model_eval_test(rnnG, 'validation', obj,csvwriter=csvwriter,calledbyTrain = True,epoch=i)
            rnnG.train()
            if (accuracy > accuracy_best):
                print("The validation set accuracy is:", accuracy)
                accuracy_best = accuracy

                # Writing down the model
                if (os.path.isdir(path)):
                    torch.save(rnnG, path + "/rnnG(validation).m")
                    torch.save(rnnD, path + "/rnnD(validation).m")
                else:
                    pathlib.Path(path).mkdir(parents=True, exist_ok=True)
                    torch.save(rnnG, path + "/rnnG(validation).m")
                    torch.save(rnnD, path + "/rnnD(validation).m")

    # Saving the models after training
    torch.save(rnnG, path + "/rnnG.m")
    torch.save(rnnD, path + "/rnnD.m")

    # plot_loss(gen_loss_pred, "Prediction loss", obj)
    plot_loss(gen_loss_tot, "Generator loss total", obj)
    plot_loss(disc_loss_tot, "Discriminator loss total", obj)

#########################################################################################################

def plot_loss(data_list, title, obj):
    '''
    #Plotting the input data
    @param data_list: A list of error values or accuracy values
    @param obj:
    @param title: A description of the datalist
    @return:
    '''
    if (title == "Generator loss total"):
        if (hasattr(obj, 'plot')):
            obj.plot += 1
        else:
            obj.plot = 1

    # plt.figure()
    plt.plot(bn.move_mean(data_list, window=100, min_count=1), label=title)
    plt.title(title + ' prefix =' + str(obj.prefix_len) + ',' + "batch = " + str(obj.batch))
    plt.legend()

    tt = str(datetime.now()).split('.')[0].split(':')
    strfile = obj.path + '/' + title + ', prefix =' + str(obj.prefix_len) + ',' + "batch = " + str(obj.batch) + str(
        obj.plot)
    plt.savefig(strfile)

    if (title == "Discriminator loss total"):
        plt.close()