import numpy as np
import torch
from typing import *
import random
from datetime import datetime


from EnvUtils import VehicleState, VehicleAction


def loadModel(model: torch.nn.Module, path: str) -> None:
    model.load_state_dict(torch.load(path))


def saveModel(model: torch.nn.Module, path: str) -> None:
    torch.save(model.state_dict(), path)


def copyModel(src_model: torch.nn.Module, dst_model) -> None:
    dst_model.load_state_dict(src_model.state_dict())
    dst_model.eval()


class MemoryTuple:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    def __init__(self):
        self.state:      VehicleState   = None
        self.action:     VehicleAction  = None
        self.reward:     float          = None
        self.next_state: VehicleState   = None
        self.done:       bool           = None


    def isComplete(self):
        return self.state is not None and \
            self.action is not None and \
            self.reward is not None and \
            self.next_state is not None and \
            self.done is not None

    def toTuple(self):
        return self.state, self.action, self.reward, self.next_state, self.done


    @classmethod
    def fromTuple(cls, tup: Tuple):
        memory = cls()
        memory.state, memory.action, memory.reward, memory.next_state, memory.done = tup
        return memory

    @classmethod
    def makeBatch(cls, memories: List["MemoryTuple"]) -> Tuple:
        states = []
        actions = []
        rewards = []
        next_states = []
        dones = []
        for memory in memories:
            states.append(memory.state)
            actions.append(memory.action)
            rewards.append(memory.reward)
            next_states.append(memory.next_state)
            dones.append(memory.done)

        state_tensors = VehicleState.makeBatch(states)
        action_tensor = VehicleAction.makeBatch(actions)
        reward_tensor = torch.tensor(rewards, dtype=torch.float32, device=cls.device)
        next_state_tensors = VehicleState.makeBatch(next_states)
        done_tensor = torch.tensor(dones, dtype=torch.bool, device=cls.device)

        result = (*state_tensors, action_tensor, reward_tensor, *next_state_tensors, done_tensor)
        return result


class MovingAverage:
    def __init__(self, window_size: int) -> None:
        self.window_size = window_size
        self.n_items = 0
        self.index_ptr = 0
        self.values = np.zeros(window_size, dtype=np.float32)

    def add(self, value: float) -> None:
        self.values[self.index_ptr] = value
        self.index_ptr = (self.index_ptr + 1) % self.window_size
        self.n_items = min(self.n_items + 1, self.window_size)

    def get(self) -> float:
        return np.mean(self.values[:self.n_items])

    def __str__(self):
        return self.get().__str__()


class MemoryList(list):
    """
    Data structure for storing memory tuples
    The environment will keep adding memory tuples to the queue in process #1
    The training process will keep sampling memory tuples from the queue in process #2
    This class is process-safe

    """
    def __init__(self, max_size: int) -> None:
        super().__init__()
        self.max_size = max_size

    def __repr__(self):
        return f"MemoryList({self.__len__()}/{self.max_size})"

    def append(self, memory: MemoryTuple) -> None:
        if self.__len__() == self.max_size:
            self.pop(0)
        super().append(memory)


    def is_empty(self) -> bool:
        return self.__len__() == 0

    def is_full(self) -> bool:
        return self.__len__() == self.max_size

    def sampleBatch(self, batch_size: int) -> Tuple:
        """
        Sample a batch of memory tuples from the queue.
        :param batch_size: batch size
        :return: (*state_tensors, action_tensor, reward_tensor, *next_state_tensors, done_tensor)
        """
        batch_data = random.sample(self, batch_size)
        batch_tensors = MemoryTuple.makeBatch(batch_data)
        return batch_tensors
    
    def save(self, folder_path: str) -> None:
        for i, memory in enumerate(self[::5]):
            memory_tuple = memory.toTuple()
            torch.save(memory_tuple, f"{folder_path}/{i:05d}.pt")


class LogWriter:
    def __init__(self, logger_title, log_dir):
        self.title = f"{logger_title:-<20}"
        self.log_path = f"{log_dir}/{logger_title}.log"

    def log(self, msg_title: str, content: str) -> None:
        """
        Write a log message to the log file and print it to the console
        :param msg_title: Title of the message, may be "WARNING", "ERROR", "INFO", "DEBUG" etc.
        :param content: Message content
        """
        msg_time = datetime.now().strftime("%Y%m%d-%H%M%S")
        message = f"<{self.title:}> [{msg_time}] [{msg_title.upper()}]: {content}"
        with open(self.log_path, "a") as f:
            f.write(message + "\n")
            f.flush()
        print(message)