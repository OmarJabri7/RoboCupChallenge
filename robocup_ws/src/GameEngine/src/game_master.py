import sys, os
sys.path.append('../../')
cwd = os.getcwd()
sys.path.append(cwd)
import inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir) 

print(f'cwd = {cwd}')
print(f'path = {sys.path}')

from tqdm import tqdm
from src.robot_model import RobotBasicModel
from src.ball_model import BallBasicModel, BallActions
# import matplotlib.pyplot as plt
from src.visualizer import BasicVisualizer
from src.game_simulator import GameSimulator
import logging


class BaseGameMaster:
    def __init__(self):
        """
        :param robot_class:
        :param number_of_teams:
        :param number_of_robots:
        :param size_of_field:
        """
        # Ego field coordinate system: located in the middle of the field,
        # positive X towards opponent's goal
        # positive Y 90deg rotated counterclockwise from X axis
        self.number_of_robots = 5
        self.number_of_teams = 2
        self.visualizer = BasicVisualizer(None, number_of_players=self.number_of_robots)
        self.simulator = None
        self.reset()

        self.full_game_length = 30000
        self.game_current_step = 0
        self.goals = [0, 0]

        self.action_buffer = [None] * self.number_of_teams
        self.action_updated = [False] * self.number_of_teams

    def reset(self):
        """
        Reset the play
        :return:
        """
        self.simulator = GameSimulator(RobotBasicModel, BallBasicModel,
                                       number_of_robots=self.number_of_robots,
                                       number_of_teams=self.number_of_teams)
        pass

    def update_robot_actions(self, team_id: int, actions: tuple):
        """
        Update the robots actions - aggregate from all agents
        :return:
        """
        self.action_updated[team_id] = True
        self.action_buffer[team_id] = actions

    def step(self):
        """
        Execute the simulation step
        :return:
        """
        self.game_current_step += 1
        logging.info(f'current game step {self.game_current_step}')
        if not all(self.action_updated):
            logging.warning("Some team have not updated the action")
        self.simulator.step(self.action_buffer)
        self.visualizer.send_game_state(*self.simulator.get_positions_for_visualizer())
        self.visualizer.display()

        if self.game_current_step >= self.full_game_length:
            self.end_game()

    def end_game(self):
        logging.info(f"End of game with result {self.goals}")

    def get_game_state(self):
        """
        Interface for the visualization
        :return:
        """
        return self.goals, self.game_current_step

    def update_goal_counter(self, goal_status):
        if goal_status != 0:
            team_id = goal_status - 1
            self.goals[team_id] += 1


ROS = True
if __name__ == "__main__" and ROS:
    import rospy
    from game_interfaces.srv import *
    from Planner.robocup_control.srv import *
    from game_interfaces.msg import *
    pass


class GameMasterClient:
    def __init__(self):
        rospy.init_node('game_master_client')
        rospy.wait_for_service(r'game_engine/game_simulation')
        try:
            self.server = rospy.ServiceProxy(r'game_engine/game_simulation', SimulationUpdate)
        except rospy.ServiceException as e:
            print("Service call failed: %s" % e)
            raise e
    def action_request(self,team_id,player_id,player_position,ball_position):
        rospy.wait_for_service("actions_return")
        try:
            self.action_service = rospy.ServiceProxy("actions_return", ActionServices)
            actions = self.action_service(team_id,player_id,player_position[0],player_position[1],ball_position[0],ball_position[1])
            return actions.left_wheel, actions.right_wheel
        except rospy.ServiceException as e:
            print("Service call failed: %s " % e)
            raise e

    def send_update_request(self, actions_list,team_id,player_id):
        team_actions = self.convert_action_list_to_team_commands(actions_list)
        rq = SimulationUpdateRequest(True, False, True,team_id,player_id,team_actions)
        resp = self.server(rq)
        return resp

    @staticmethod
    def convert_action_list_to_team_commands(action_list):
        out = []
        for team_id, team_actions in enumerate(action_list):
            tc = TeamCommand()
            tc.team_id = team_id
            for player_idx, (lw, rw) in enumerate(team_actions):
                tc.players_commands[player_idx].left_rpm = lw
                tc.players_commands[player_idx].right_rpm = rw
                tc.players_commands[player_idx].extra_action = 0
            out.append(tc)
        return out


if __name__ == "__main__" and ROS:
    GMC = GameMasterClient()
    actions = [[(0,0), (0, 0), (0, 0), (0,0), (0, 0)],
               [(0, 0), (0, 0), (0, 0), (0, 0), (0,0)]]
    team_id = 0
    player_id = 1
    for i in tqdm(range(5000)):
        response = GMC.send_update_request(actions,team_id,player_id)
        print(response)
        player_position = [response.player_x,response.player_y]
        ball_position = [response.ball_x,response.ball_y]
        action = GMC.action_request(team_id,player_id,player_position,ball_position)
        actions[team_id][player_id] = action



class TestGameMaster:
    @staticmethod
    def test_game_master_initialization():
        pass

    @staticmethod
    def test_game_with_simple_actions():
        pass


if not ROS and __name__ == "__main__":
    from goalkeeper_controller import GoalkeeperController
    from robot_control import Goal

    game_master = BaseGameMaster()
    team01Attacker01 = GoalkeeperController(game_master.simulator.get_robot_model(0, 0), game_master.simulator.ball)
    team01GoalkeeperGate = GoalkeeperController(game_master.simulator.get_robot_model(0, 4), game_master.simulator.ball)
    team02Attacker01 = GoalkeeperController(game_master.simulator.get_robot_model(1, 4), game_master.simulator.ball)
    actions = [(0, 0), (0, 0), (0, 0), (0, 0), (0, 0)]
    kick_done = False

    while True:
        game_master.update_robot_actions(0, [team01Attacker01.get_action(Goal.ChaseBall), (0, 0), (0, 0), (0, 0), team01GoalkeeperGate.get_action(Goal.RotateToPoint)])
        game_master.update_robot_actions(1, [(0,0), (0, 0), (0, 0), (0, 0), team02Attacker01.get_action(Goal.ChaseBall)])
        # game_master.update_robot_actions(0, [(0,0), (0, 0), (0, 0), (0, 0), (0, 0)])
        # game_master.update_robot_actions(1, [(0,0),  (0, 0), (0, 0), (0, 0), (0,0)])
        game_master.step()

