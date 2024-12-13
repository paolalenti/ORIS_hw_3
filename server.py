import pickle
import socket
import threading

HOST = "127.0.0.1"
PORT = 10000


class GameRoom:
    def __init__(self, room_name, server):
        self.game_server = server
        self.room_name = room_name
        self.semaphore = threading.Semaphore(value=2)
        self.used_cities = []
        self.clients = []
        self.turn = 0
        self.game_condition = False
        self.condition = threading.Condition()

    def broadcast(self, msg):
        for client in self.clients:
            client.send(pickle.dumps(msg))

    def run(self, client, client_address, client_name):
        self.semaphore.acquire()
        client.send(pickle.dumps(f"welcome to room, {client_name} from {client_address}"))
        self.clients.append(client)
        if len(self.clients) == 2:
            self.game_condition = True
        threading.Thread(target=self.play_game, args=(client, client_address, client_name)).start()

    def play_game(self, client, client_address, client_name):
        if not self.game_condition:
            client.send(pickle.dumps(f"wait for second player, {client_name}"))

        while not self.game_condition:
            pass

        client_idx = self.clients.index(client)
        opponent_idx = 1 - client_idx

        if client_idx == 0:
            client.send(pickle.dumps("second player is here"))
            self.broadcast("game is starting")

        while self.game_condition:
            if not self.check_turn(client_idx):
                client.send(pickle.dumps("wait for your turn"))
                with self.condition:
                    self.condition.wait()

            timer = threading.Timer(15, self.end_game,
                                    args=(client, client_address, client_name, client_idx, opponent_idx))
            timer.start()

            flag = True
            while flag:
                city = pickle.loads(client.recv(1024))
                if city.lower() == "exit":
                    timer.cancel()
                    self.end_game(client, client_address, client_name, client_idx, opponent_idx)
                    with self.condition:
                        self.condition.notify()
                    break

                flag = not self.valid_city(client, city)

            timer.cancel()

            if not flag:
                data = pickle.dumps(f'opponent city: "{city}"\n'
                                    f'your city must starts on letter: "{city[-1]}"')
                self.clients[opponent_idx].send(data)
                self.turn = opponent_idx
                with self.condition:
                    self.condition.notify()

        if client in self.clients:
            self.turn = 0
            self.clients = []
            self.semaphore.release()
            threading.Thread(target=self.game_server.handle_client, args=(client, client_address, client_name)).start()

    def end_game(self, client, client_address, client_name, client_idx, opponent_idx):
        self.game_condition = False
        self.turn = -1
        if len(self.clients) == 2:
            client.send(pickle.dumps("you lose ^-^"))
            self.clients[opponent_idx].send(pickle.dumps("you win"))
        self.clients.pop(client_idx)
        self.used_cities = []
        self.semaphore.release()
        print("game over")
        threading.Thread(target=self.game_server.handle_client, args=(client, client_address, client_name)).start()

    def valid_city(self, client, city):
        if not self.used_cities:
            self.used_cities.append(city)
            return True
        elif city[0] == self.used_cities[-1][-1] and city not in self.used_cities:
            self.used_cities.append(city)
            return True
        else:
            (client.send(pickle.dumps(
                f'city starts with wrong letter or it is in "named before", your last letter is {self.used_cities[-1][-1]}')))

    def check_turn(self, idx):
        if self.turn == idx:
            return True

        return False


class GameServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((HOST, PORT))
        self.server_socket.listen(10)
        self.client_names = set()
        self.clients = {} # {client_name: client}
        self.banned_clients = set()
        self.lock = threading.Lock()
        self.rooms = dict()  # {room_name: GameRoom()}

    def start(self):
        print("server is running")
        while True:
            client, client_address = self.server_socket.accept()
            print(f"Connected: {client_address}")
            if client not in self.banned_clients:
                threading.Thread(target=self.handle_client, args=(client, client_address, None)).start()

    def handle_client(self, client, client_address, name):
        client_name = name

        while client_name is None:
            client.send(pickle.dumps("Your name: "))
            suggested_name = str(pickle.loads(client.recv(1024)))
            with self.lock:
                if suggested_name not in self.client_names:
                    client_name = str(suggested_name)
                    self.client_names.add(client_name)
                else:
                    client.send(pickle.dumps("Name already in use("))

        self.clients[client_name] = client

        menu = ("make choice: \n"
                "1.create room \n"
                "2.join room \n"
                "3.list_of_rooms \n"
                "4.exit server \n"
                "5.delete room \n"
                "6.ban")
        client.send(pickle.dumps(menu))

        while True:
            msg = str(pickle.loads(client.recv(1024)))
            if msg == "1":
                client.send(pickle.dumps("room_name: "))
                room_name = str(pickle.loads(client.recv(1024)))
                self.create_room(client, client_address, client_name, room_name)
                break
            elif msg == "2":
                client.send(pickle.dumps("room_name: "))
                room_name = str(pickle.loads(client.recv(1024)))
                if self.join_room(client, client_address, client_name, room_name):
                    break
                else:
                    client.send(pickle.dumps("room doesnt exist or room is full"))
            elif msg == "3":
                lst = list(self.rooms.keys())
                if len(lst) == 0:
                    client.send(pickle.dumps("no rooms"))
                else:
                    client.send(pickle.dumps(lst))
                client.send(pickle.dumps(menu))
            elif msg == "4":
                print("bye, loser")
                client.close()
                break
            elif msg == "5":
                client.send(pickle.dumps("room_name: "))
                room_name = str(pickle.loads(client.recv(1024)))
                if self.delete_room(room_name):
                    client.send(pickle.dumps("room has been deleted"))
                else:
                    client.send(pickle.dumps("room doesnt exist or room is not empty"))
            elif msg =="6":
                client.send(pickle.dumps("client_name: "))
                ban_name = str(pickle.loads(client.recv(1024)))
                if ban_name in self.client_names:
                    client.send(pickle.dumps("reason???"))
                    reason = pickle.loads(client.recv(1024))
                    print(f'{client_name} запрашивает бан игроку {ban_name} \nпричина: {reason}')
                    answer = input('ok or not:')
                    if answer == "ok":
                        self.banned_clients.add(ban_name)
                        self.clients.get(ban_name).close()
                        client.send(pickle.dumps("banned xD"))
                    else:
                        client.send(pickle.dumps("NO."))
                else:
                    client.send(pickle.dumps("client with this name doesnt exist"))

            else:
                client.send(pickle.dumps("can you write 1 or 2 or 3 or 4 or 5? its not difficult)"))

    def create_room(self, client, client_address, client_name, room_name):
        new_room = GameRoom(room_name, self)
        self.rooms[room_name] = new_room
        new_room.run(client, client_address, client_name)

    def join_room(self, client, client_address, client_name, room_name):
        curr_room = self.rooms.get(room_name)
        if curr_room is not None and curr_room.game_condition is False:
            curr_room.run(client, client_address, client_name)
            return True

    def delete_room(self, room_name):
        curr_room = self.rooms.get(room_name)
        if curr_room is not None and len(curr_room.clients) == 0:
            self.rooms.pop(room_name)
            return True


server = GameServer()
server.start()
