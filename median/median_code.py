import numpy as np
import matplotlib.pyplot as plt
import random
import time

num_class = 10
num_feature = 28 * 28
num_train = 60000
num_test = 10000
num_machines = 20
batch_size = 32

num_iter = 5000
exit_byzantine = True
num_byz = 8


def cal_total_grad(X, Y, theta, weight_lambda):

    """
    :param X: shape(num_samples, features + 1)
    :param Y: labels' one_hot array, shape(num_samples, features + 1)
    :param theta: shape (num_classes, feature+1)
    :param weight_lambda: scalar
    :return: grad, shape(num_classes, feature+1)
    """
    m = X.shape[0]
    t = np.dot(theta, X.T)
    t = t - np.max(t, axis=0)
    pro = np.exp(t) / np.sum(np.exp(t), axis=0)
    total_grad = -np.dot((Y.T - pro), X) / m + weight_lambda * theta
    return total_grad


def cal_loss(X, Y, theta, weight_lambda):

    m = X.shape[0]
    t1 = np.dot(theta, X.T)
    t1 = t1 - np.max(t1, axis=0)
    t = np.exp(t1)
    tmp = t / np.sum(t, axis=0)
    loss = -np.sum(Y.T * np.log(tmp)) / m + weight_lambda * np.sum(theta ** 2) / 2
    return loss


def cal_acc(test_x, test_y, theta):

    pred = []
    num = 0
    m = test_x.shape[0]
    for i in range(m):
        t1 = np.dot(theta, test_x[i])
        t1 = t1 - np.max(t1, axis=0)
        pro = np.exp(t1) / np.sum(np.exp(t1), axis=0)
        index = np.argmax(pro)
        if index == test_y[i]:
            num += 1
    acc = float(num) / m
    return acc, pred


def my_median(grad_li):

    grad_array = np.array(grad_li)
    grad_array = grad_array.reshape(num_machines, num_class * (num_feature + 1))
    med = np.median(grad_array, axis=0)
    med = med.reshape(num_class, num_feature + 1)
    return med

class Machine:

    def __init__(self, data_x, data_y, machine_id):

        self.data_x = data_x
        self.data_y = data_y
        self.machine_id = machine_id

    def calc_gradient(self, theta, weight_lambda, id):

        m = self.data_x.shape[0]
        id = random.randint(0, m - batch_size)
        grad = cal_total_grad(self.data_x[id:(id + batch_size)], self.data_y[id:(id + batch_size)], theta,
                              weight_lambda)
        if (exit_byzantine == True and self.machine_id >= num_machines - num_byz):
            # grad = -grad
            grad = np.random.standard_normal((num_class, num_feature+1))*10000
            # grad = np.ones_like(theta)*100
        return grad


class Parameter_server:

    def __init__(self):
        self.theta_li = []
        self.total_grad = []
        self.acc_li = []
        self.time_li = []

        path = "../data/mnist/"
        train_img = np.load(path + 'train_img.npy')  # shape(60000, 784)
        train_lbl = np.load(path + 'train_lbl.npy')  # shape(60000,)
        one_train_lbl = np.load(path + 'one_train_lbl.npy')  # shape(10, 60000)
        test_img = np.load(path + 'test_img.npy')  # shape(10000, 784)
        test_lbl = np.load(path + 'test_lbl.npy')  # shape(10000,)

        bias_train = np.ones(num_train)
        train_img_bias = np.column_stack((train_img, bias_train))

        bias_test = np.ones(num_test)
        test_img_bias = np.column_stack((test_img, bias_test))

        self.test_img_bias = test_img_bias
        self.test_lbl = test_lbl
        self.train_img_bias = train_img_bias
        self.one_train_lbl = one_train_lbl

        samples_per_machine = num_train / num_machines

        self.machines = []
        for i in range(num_machines):
            new_machine = Machine(train_img_bias[i * samples_per_machine:(i + 1) * samples_per_machine, :],
                                  one_train_lbl[i * samples_per_machine:(i + 1) * samples_per_machine], i)
            self.machines.append(new_machine)

        ###############   every 2 machine share the same digit image
        # for i in range(num_class):
        #     s1 = '../data/mnist/2/train_img' + str(i) + '.npy'
        #     s2 = '../data/mnist/2/one_train_lbl' + str(i) + '.npy'
        #     train = np.load(s1)
        #     label = np.load(s2)
        #     size = train.shape[0]
        #     num1 = size / 2
        #     tmp_bias = np.ones(size)
        #     train_bias = np.column_stack((train, tmp_bias))
        #     new_machine1 = Machine(train_bias[0:num1, :], label[0:num1, :], i*2)
        #     new_machine2 = Machine(train_bias[num1:, :], label[num1:, :], i * 2 + 1)
        #     self.machines.append(new_machine1)
        #     self.machines.append(new_machine2)

    def broadcast(self, x, wei_lambda, id):

        grad_li = []
        for mac in self.machines:
            grad_li.append(mac.calc_gradient(x, wei_lambda, id))
        return grad_li

    def train(self, init_theta, alpha, wei_lambda):

        self.theta_li.append(init_theta)
        sample_per_machine = num_train / num_machines

        alpha = 0.0001
        d = 0.00005
        wei_lambda = 0.01
        start = time.clock()
        for i in range(num_iter):
            alpha = d / np.sqrt(i + 1)
            id = i % sample_per_machine
            grad_li = self.broadcast(self.theta_li[-1], wei_lambda, id)
            grad = my_median(grad_li)
            new_x = self.theta_li[-1] - alpha * grad
            self.theta_li.append(new_x)
            # total = cal_total_grad(self.train_img_bias, self.one_train_lbl, new_x, wei_lambda)
            # self.total_grad.append(np.linalg.norm(total))
            if (i + 1) % 10 == 0:
                iter_time = time.clock()
                self.time_li.append(iter_time - start)
                acc, _ = cal_acc(self.test_img_bias, self.test_lbl, new_x)
                self.acc_li.append(acc)
                print "step:", i, "acc:", acc
        print "train end!"

    def plot(self):

        s1 = 'gaussian/q8'
        # np.save('./result/machine20/fault/same_attack4/q4/' + s1 + '/grad_norm_li.npy', self.total_grad)
        # np.save('./result/machine20/fault/' + s1 + '/acc_li.npy', self.acc_li)

        plt.plot(np.arange(len(self.acc_li)) * 10, self.acc_li)
        plt.xlabel('iter')
        plt.ylabel('accuracy')
        # plt.savefig('./result/machine20/fault/' + s1 + '/acc.jpg')
        plt.show()

        # plt.semilogy(np.arange(num_iter), self.total_grad)
        # plt.xlabel('iter')
        # plt.ylabel('log||grad||')
        # plt.savefig('./result/machine20/fault/same_attack4/q4/' + s1 + '/grad_norm.jpg')
        # plt.show()


def init():
    server = Parameter_server()
    return server


def main():
    server = init()
    init_x = np.zeros((num_class, num_feature + 1))
    alpha = 0.00005
    wei_lam = 0.01
    server.train(init_x, alpha, wei_lam)
    server.plot()


if __name__ == "__main__":
    main()











