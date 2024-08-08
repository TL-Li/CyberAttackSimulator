import argparse
import os
import sys

import tyro
import wandb
from stable_baselines3 import A2C, DQN, PPO
from stable_baselines3.a2c import MlpPolicy as A2CMlp
from stable_baselines3.common.callbacks import (
    EvalCallback, StopTrainingOnNoModelImprovement)
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.dqn import MlpPolicy as DQNMlp
from stable_baselines3.ppo import MlpPolicy as PPOMlp
from wandb.integration.sb3 import WandbCallback

sys.path.append(os.getcwd())
from cyberattacksim.envs.generic.core.action_loops import ActionLoop
from cyberattacksim.utils.env_utils import create_env
from cyberattacksim.utils.file_utils import (load_yaml_config,
                                             update_dataclass_from_dict)
from cyberattacksim.utils.rl_args import (A2CArguments, DQNArguments,
                                          PPOArguments, RLArguments)


def main(args: RLArguments) -> None:
    # Initialize ArgumentParser
    parser = argparse.ArgumentParser(description='Cyber Attack Sim')
    parser.add_argument(
        '--algo_name',
        type=str,
        choices=[
            'dqn',
            'a2c',
            'ppo',
        ],
        default='dqn',
        help="Name of the algorithm. Defaults to 'dqn'",
    )
    parser.add_argument(
        '--env_id',
        type=str,
        default='default_18_node_network',
        help="The environment name. Defaults to 'CartPole-v0'",
    )
    # directories
    curr_path = os.getcwd()
    # Load YAML configuration
    config_file = os.path.join(curr_path, 'examples/configs/config.yaml')
    config = load_yaml_config(config_file)
    # Parse arguments
    run_args = parser.parse_args()
    if run_args.algo_name == 'dqn':
        algo_args: DQNArguments = tyro.cli(DQNArguments)
    elif run_args.algo_name == 'A2C':
        algo_args = tyro.cli(A2CArguments)
    elif run_args.algo_name == 'ppo':
        algo_args: PPOArguments = tyro.cli(PPOArguments)
    else:
        raise NotImplementedError

    # Extract Algo-specific settings
    if run_args.algo_name in config:
        algo_config = config.get(run_args.algo_name)
        env_config = algo_config.get(run_args.env_id)
    else:
        env_config = {}
        print(
            'No configuration found for {}, {} in {}. Using default settings.'.
            format(run_args.algo_name, run_args.env_id, config_file))

    # Update parser with YAML configuration
    args = update_dataclass_from_dict(algo_args, env_config)

    # set file path
    log_dir = os.path.join(args.work_dir, args.env_id)
    model_dir = os.path.join(log_dir, args.algo_name)
    tf_log_dir = os.path.join(model_dir, 'tf_logs')
    model_name = os.path.join(model_dir, args.algo_name + '_model')
    media_dir = os.path.join(log_dir, args.algo_name, 'media')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    run = wandb.init(dir=log_dir,
                     project=args.project,
                     name=args.env_id,
                     sync_tensorboard=True)
    env = create_env(env_id=args.env_id)
    # setup the monitor to check the training
    env = Monitor(env, model_name)
    # define callback to stop the trainingX
    stop_train_callback = StopTrainingOnNoModelImprovement(
        max_no_improvement_evals=5, min_evals=10, verbose=1)
    print(stop_train_callback)
    eval_callback = EvalCallback(
        env,
        n_eval_episodes=10,
        eval_freq=1000,  # eval_freq
        log_path=model_dir,  # save the logs
        best_model_save_path=model_dir,  # save the model
        deterministic=True,
        render=False,
        verbose=1,
    )
    wandb_callback = WandbCallback(
        model_save_path=model_dir,
        model_save_freq=1000,
        verbose=2,
    )
    run_args = parser.parse_args()
    if run_args.algo_name == 'dqn':
        agent = DQN(
            policy=DQNMlp,
            env=env,
            learning_rate=args.learning_rate,
            buffer_size=args.buffer_size,
            learning_starts=args.learning_starts,
            batch_size=args.batch_size,
            train_freq=args.train_freq,
            target_update_interval=args.target_update_interval,
            tensorboard_log=tf_log_dir,
            verbose=1,
        )

    elif run_args.algo_name == 'A2C':
        agent = A2C(
            policy=A2CMlp,
            env=env,
            learning_rate=args.learning_rate,
            n_steps=args.n_steps,
            gamma=args.gamma,
            gae_lambda=args.gae_lambda,
            normalize_advantage=args.normalize_advantage,
            tensorboard_log=tf_log_dir,
            verbose=1,
        )
    elif run_args.algo_name == 'ppo':
        agent = PPO(
            policy=PPOMlp,
            env=env,
            learning_rate=args.learning_rate,
            n_steps=2048,
            batch_size=args.batch_size,
            n_epochs=args.n_epochs,
            gamma=args.gamma,
            gae_lambda=args.gae_lambda,
            clip_range=args.clip_range,
            normalize_advantage=True,
            tensorboard_log=tf_log_dir,
            verbose=1,
        )

    # Train the agent
    agent.learn(
        total_timesteps=args.total_timesteps,
        callback=[eval_callback, wandb_callback],
        log_interval=args.log_interval,
        eval_freq=args.eval_freq,
        progress_bar=True,
    )
    evaluate_policy(agent, env, n_eval_episodes=10)
    # save the trained-converged model
    agent.save(model_name)
    run.finish()
    # visualize the trained-converged model
    loop = ActionLoop(env, agent, episode_count=5)
    loop.gif_action_loop(
        save_gif=True,
        render_network=True,
        save_webm=True,
        gif_output_directory=media_dir,
        webm_output_directory=media_dir,
    )


if __name__ == '__main__':
    args: DQNArguments = tyro.cli(DQNArguments)
    main(args)
