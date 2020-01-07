#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#   @Time    : 2020/1/2 10:41
#   @Author  : PlatON-Developer
#   @Site    : https://github.com/PlatONnetwork/
import os
import pytest
from decimal import Decimal

from common.log import log
from common.key import mock_duplicate_sign
from tests.lib.genesis import to_genesis
from tests.lib.client import Client
from tests.lib.utils import assert_code
from tests.ppos.conftest import create_staking, calculate


def calculate_switch_block(node, economic):
    block_number = node.block_number
    return int(block_number / economic.settlement_size) * economic.settlement_size


def calculate_reward(block_reward, staking_reward, block_num, reward):
    delegate_reward = int(Decimal(str(staking_reward))*Decimal(str(reward))/Decimal(str(10000)) + Decimal(str(int(Decimal(str(block_reward))*Decimal(str(reward))/Decimal(str(10000))))) * Decimal(str(block_num)))
    total_reward = int(Decimal(str(staking_reward)) + Decimal(str(block_reward)) * Decimal(str(block_num)))
    return total_reward, delegate_reward


@pytest.mark.P0
def test_DG_TR_001(client_consensus, reset_environment):
    """
    调整内置节点分红比例，验证节点产生的总委托奖励
    :param client_consensus:
    :return:
    """
    reward = 1000
    economic = client_consensus.economic
    node = client_consensus.node
    candidate_info = client_consensus.ppos.getCandidateInfo(node.node_id)
    log.info("first candidate info:{}".format(candidate_info))
    assert candidate_info["Ret"]["RewardPer"] == 0
    result = client_consensus.staking.edit_candidate(economic.cfg.DEVELOPER_FOUNDATAION_ADDRESS, economic.cfg.INCENTIVEPOOL_ADDRESS, reward_per=reward)
    assert_code(result, 0)
    candidate_info = client_consensus.ppos.getCandidateInfo(node.node_id)
    log.info("second candidate info:{}".format(candidate_info))
    assert candidate_info["Ret"]["RewardPer"] == 0
    edit_after_balance = node.eth.getBalance(economic.cfg.INCENTIVEPOOL_ADDRESS)
    log.info("Get the balance before editing：{}".format(edit_after_balance))
    client_consensus.economic.wait_settlement_blocknum(node)
    candidate_info = client_consensus.ppos.getCandidateInfo(node.node_id)
    log.info("last candidate info:{}".format(candidate_info))
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0
    assert node.eth.getBalance(economic.cfg.INCENTIVEPOOL_ADDRESS) - edit_after_balance == 0


@pytest.mark.P0
def test_DG_TR_002(client_consensus, reset_environment):
    """
    调整内置节点收益地址和分红比例，验证节点产生的总委托奖励
    :param client_consensus:
    :return:
    """
    reward = 1000
    economic = client_consensus.economic
    node = client_consensus.node
    candidate_info = client_consensus.ppos.getCandidateInfo(node.node_id)
    log.info("View built-in node information：{}".format(candidate_info))
    assert candidate_info["Ret"]["RewardPer"] == 0
    log.info("editing built in nodes")
    result = client_consensus.staking.edit_candidate(economic.cfg.DEVELOPER_FOUNDATAION_ADDRESS, economic.cfg.INCENTIVEPOOL_ADDRESS,
                                                     reward_per=reward)
    assert_code(result, 0)
    candidate_info = client_consensus.ppos.getCandidateInfo(node.node_id)
    log.info("Verify the modification")
    assert candidate_info["Ret"]["RewardPer"] == 0
    assert candidate_info["Ret"]["BenefitAddress"] == economic.cfg.INCENTIVEPOOL_ADDRESS
    log.info("waiting for a settlement cycle")
    economic.wait_settlement_blocknum(node)
    candidate_info = client_consensus.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0


@pytest.mark.P1
def test_DG_TR_003(staking_node_client):
    """
    调整非内置节点分红比例，验证节点产生的总委托奖励
    :param staking_node_client:
    :return:
    """
    economic = staking_node_client.economic
    node = staking_node_client.node
    result = staking_node_client.delegate.delegate(0, staking_node_client.delegate_address)
    assert_code(result, 0)
    reward = 2000
    log.info("modify node dividend ratio")
    result = staking_node_client.staking.edit_candidate(staking_node_client.staking_address,
                                                        staking_node_client.staking_address, reward_per=reward)
    assert_code(result, 0)
    candidate_info = staking_node_client.ppos.getCandidateInfo(node.node_id)
    log.info("check dividend ratio")
    assert candidate_info["Ret"]["RewardPer"] == staking_node_client.reward
    assert candidate_info["Ret"]["NextRewardPer"] == reward
    economic.wait_settlement_blocknum(node)
    block_reward, staking_reward = economic.get_current_year_reward(node)
    log.info("query block reward and pledge reward：{}，{}".format(block_reward, staking_reward))
    economic.wait_settlement_blocknum(node)
    candidate_info = staking_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["RewardPer"] == reward
    candidate_info = staking_node_client.ppos.getCandidateInfo(node.node_id)
    delegate_reward = economic.calculate_delegate_reward(node, block_reward, staking_reward)
    log.info("the total commission reward is:{}".format(delegate_reward))
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward


@pytest.mark.P1
def test_DG_TR_004(staking_node_client):
    """
    节点无委托时，验证节点产生的总委托奖励（犹豫期）
    :param staking_node_client:
    :return:
    """
    node = staking_node_client.node
    candidate_info = staking_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0


@pytest.mark.P1
def test_DG_TR_005(global_test_env, reset_environment, staking_cfg):
    """
    节点无委托时，验证节点产生的总委托奖励（候选人）
    :param global_test_env:
    :param reset_environment:
    :param staking_cfg:
    :return:
    """
    log.info("modify verification number")
    genesis_cfg = global_test_env.genesis_config
    genesis = to_genesis(genesis_cfg)
    genesis.economicModel.staking.maxValidators = 4
    genesis_file = os.path.join(global_test_env.cfg.env_tmp, "dg_tr_005_genesis.json")
    genesis.to_file(genesis_file)
    global_test_env.deploy_all(genesis_file)
    node = global_test_env.get_a_normal_node()
    client = Client(global_test_env, node, staking_cfg)
    log.info("pledge a node")
    create_staking(client, reward=1000)
    client.economic.wait_settlement_blocknum(node)
    candidate_info = client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0


@pytest.mark.P0
def test_DG_TR_006(staking_node_client):
    """
    节点无委托时，验证节点产生的总委托奖励（验证人）
    :param staking_node_client:
    :return:
    """
    economic = staking_node_client.economic
    node = staking_node_client.node
    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(staking_node_client.staking_address, switch_block)
    log.info("starting amount:{}".format(start_balance))
    block_reward, staking_reward = economic.get_current_year_reward(node)
    log.info("query block reward and pledge reward：{}，{}".format(block_reward, staking_reward))
    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    end_balance = node.eth.getBalance(staking_node_client.staking_address, switch_block)
    log.info("end balance:{}".format(end_balance))
    block_num = economic.get_number_blocks_in_interval(node)
    log.info("This node generates blocks in this settlement cycle:{}".format(block_num))
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, reward=0)
    assert total_reward == end_balance - start_balance


def test_DG_TR_007(delegate_node_client):
    """
    节点有委托时，验证节点产生的总委托奖励（犹豫期）
    :param delegate_node_client:
    :return:
    """
    node = delegate_node_client.node
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0
    delegate_info = node.ppos.getDelegateInfo(candidate_info["Ret"]["StakingBlockNum"], delegate_node_client.delegate_address, node.node_id)
    assert delegate_info["Ret"]["CumulativeIncome"] == 0


def test_DG_TR_008(global_test_env, reset_environment, staking_cfg):
    """
    节点有委托时，验证节点产生的总委托奖励（候选人）
    :param global_test_env:
    :param reset_environment:
    :param staking_cfg:
    :return:
    """
    log.info("modify verification number")
    genesis_cfg = global_test_env.genesis_config
    genesis = to_genesis(genesis_cfg)
    genesis.economicModel.staking.maxValidators = 4
    genesis_file = os.path.join(global_test_env.cfg.env_tmp, "dg_tr_005_genesis.json")
    genesis.to_file(genesis_file)
    global_test_env.deploy_all(genesis_file)
    node = global_test_env.get_a_normal_node()
    client = Client(global_test_env, node, staking_cfg)
    log.info("pledge a node")
    staking_address, delegate_address = create_staking(client, reward=1000)
    result = client.delegate.delegate(0, delegate_address)
    assert_code(result, 0)
    client.economic.wait_settlement_blocknum(node)
    candidate_info = client.ppos.getCandidateInfo(node.node_id)
    log.info("candidate info:{}".format(candidate_info))
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0
    delegate_info = node.ppos.getDelegateInfo(candidate_info["Ret"]["StakingBlockNum"], delegate_address, node.node_id)
    log.info("delegate info:{}".format(delegate_info))
    assert delegate_info["Ret"]["CumulativeIncome"] == 0


@pytest.mark.P0
def test_DG_TR_009(delegate_node_client):
    """
    节点有委托时，验证节点产生的总委托奖励（验证人）
    :param delegate_node_client:
    :return:
    """
    node = delegate_node_client.node
    economic = delegate_node_client.economic

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(delegate_node_client.staking_address, switch_block)
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    end_balance = node.eth.getBalance(delegate_node_client.staking_address, switch_block)
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, delegate_node_client.reward)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward
    assert candidate_info["Ret"]["RewardPer"] == delegate_node_client.reward
    assert end_balance - start_balance == total_reward - delegate_reward


@pytest.mark.P0
def test_DG_TR_010(client_new_node, reset_environment):
    """
    验证节点分红比例设置为0‱，验证分红池和节点收益
    :param client_new_node:
    :param reset_environment:
    :return:
    """
    reward = 0
    node = client_new_node.node
    economic = client_new_node.economic
    staking_address, delegate_address = create_staking(client_new_node, reward)
    result = client_new_node.delegate.delegate(0, delegate_address)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(staking_address, switch_block)
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    block_num = economic.get_number_blocks_in_interval(node)
    switch_block = calculate_switch_block(node, economic)
    end_balance = node.eth.getBalance(staking_address, switch_block)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, reward)
    assert end_balance - start_balance == total_reward


def create_staking_dif_ben(client, reward):
    amount = calculate(client.economic.create_staking_limit, 5)
    staking_amount = calculate(client.economic.create_staking_limit, 2)
    staking_address, _ = client.economic.account.generate_account(client.node.web3, amount)
    ben_address, _ = client.economic.account.generate_account(client.node.web3, 0)
    delegate_address, _ = client.economic.account.generate_account(client.node.web3, client.economic.add_staking_limit * 5)
    result = client.staking.create_staking(0, ben_address, staking_address, amount=staking_amount, reward_per=reward)
    assert_code(result, 0)
    return staking_address, delegate_address, ben_address


def test_DG_TR_011(client_new_node, reset_environment):
    """
    在委托后调整分红比例，验证分红池和节点收益
    :param client_new_node:
    :return:
    """
    reward = 1000
    node = client_new_node.node
    economic = client_new_node.economic
    staking_address, delegate_address, ben_address = create_staking_dif_ben(client_new_node, 0)

    economic.wait_settlement_blocknum(node)
    result = client_new_node.delegate.delegate(0, delegate_address)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    block_reward, staking_reward = economic.get_current_year_reward(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(ben_address, switch_block)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0
    result = client_new_node.staking.edit_candidate(staking_address,
                                                    ben_address, reward_per=reward)
    assert_code(result, 0)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["NextRewardPer"] == reward

    economic.wait_settlement_blocknum(node)
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, reward)
    end_balance = node.eth.getBalance(ben_address, switch_block + economic.settlement_size)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0
    assert end_balance - start_balance == total_reward
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    delegate_reward = economic.calculate_delegate_reward(node, block_reward, staking_reward)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward
    end_balance_two = node.eth.getBalance(ben_address, switch_block + economic.settlement_size + economic.settlement_size)
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, reward)
    assert end_balance_two - end_balance == total_reward - delegate_reward


def test_DG_TR_012(client_new_node, reset_environment):
    """
    在赎回部分委托后调整分红比例，验证分红池和节点收益
    :param client_new_node:
    :return:
    """
    reward = 1000
    node = client_new_node.node
    economic = client_new_node.economic
    staking_address, delegate_address, ben_address = create_staking_dif_ben(client_new_node, 0)

    economic.wait_settlement_blocknum(node)
    result = client_new_node.delegate.delegate(0, delegate_address, amount=economic.delegate_limit * 2)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    block_reward, staking_reward = economic.get_current_year_reward(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(ben_address, switch_block)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0
    result = client_new_node.staking.edit_candidate(staking_address,
                                                    ben_address, reward_per=reward)
    assert_code(result, 0)
    result = client_new_node.delegate.withdrew_delegate(candidate_info["Ret"]["StakingBlockNum"], delegate_address)
    assert_code(result, 0)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["NextRewardPer"] == reward

    economic.wait_settlement_blocknum(node)
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, 0)
    end_balance = node.eth.getBalance(ben_address, switch_block + economic.settlement_size)
    assert end_balance - start_balance == total_reward
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    delegate_reward = economic.calculate_delegate_reward(node, block_reward, staking_reward)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward
    end_balance_two = node.eth.getBalance(ben_address,
                                          switch_block + economic.settlement_size + economic.settlement_size)
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, reward)
    assert end_balance_two - end_balance == total_reward - delegate_reward


def test_DG_TR_013(client_new_node, reset_environment):
    """
    在赎回全部委托后调整分红比例，验证分红池和节点收益
    :param client_new_node:
    :return:
    """
    reward = 1000
    node = client_new_node.node
    economic = client_new_node.economic
    staking_address, delegate_address, ben_address = create_staking_dif_ben(client_new_node, 0)

    economic.wait_settlement_blocknum(node)
    result = client_new_node.delegate.delegate(0, delegate_address)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    block_reward, staking_reward = economic.get_current_year_reward(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(ben_address, switch_block)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0
    result = client_new_node.staking.edit_candidate(staking_address,
                                                    ben_address, reward_per=reward)
    assert_code(result, 0)
    result = client_new_node.delegate.withdrew_delegate(candidate_info["Ret"]["StakingBlockNum"], delegate_address)
    assert_code(result, 0)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["NextRewardPer"] == reward

    economic.wait_settlement_blocknum(node)
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, 0)
    end_balance = node.eth.getBalance(ben_address, switch_block + economic.settlement_size)
    assert end_balance - start_balance == total_reward
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    delegate_reward = 0
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward
    end_balance_two = node.eth.getBalance(ben_address,
                                          switch_block + economic.settlement_size + economic.settlement_size)
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, 0)
    assert end_balance_two - end_balance == total_reward


def test_DG_TR_014(client_new_node, reset_environment):
    """
    在领取分红后调整分红比例，验证分红池和节点收益
    :param client_new_node:
    :return:
    """
    reward = 1000
    node = client_new_node.node
    economic = client_new_node.economic
    staking_address, delegate_address, ben_address = create_staking_dif_ben(client_new_node, 0)

    economic.wait_settlement_blocknum(node)
    result = client_new_node.delegate.delegate(0, delegate_address)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    block_reward, staking_reward = economic.get_current_year_reward(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(ben_address, switch_block)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0
    result = client_new_node.staking.edit_candidate(staking_address,
                                                    ben_address, reward_per=reward)
    assert_code(result, 0)
    result = client_new_node.delegate.withdraw_delegate_reward(delegate_address)
    assert_code(result, 0)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["NextRewardPer"] == reward

    economic.wait_settlement_blocknum(node)
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, 0)
    end_balance = node.eth.getBalance(ben_address, switch_block + economic.settlement_size)
    assert end_balance - start_balance == total_reward
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, reward)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward
    end_balance_two = node.eth.getBalance(ben_address,
                                          switch_block + economic.settlement_size + economic.settlement_size)
    block_num = economic.get_number_blocks_in_interval(node)
    assert end_balance_two - end_balance == total_reward


@pytest.mark.P0
def test_DG_TR_015(client_new_node, reset_environment):
    """
    验证节点分红比例设置为10000‱，验证分红池和节点收益
    :param client_new_node:
    :param reset_environment:
    :return:
    """
    reward = 10000
    node = client_new_node.node
    economic = client_new_node.economic
    staking_address, delegate_address = create_staking(client_new_node, reward)
    result = client_new_node.delegate.delegate(0, delegate_address)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(staking_address, switch_block)
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["RewardPer"] == reward
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, reward)
    delegate_info = node.ppos.getDelegateInfo(candidate_info["Ret"]["StakingBlockNum"], delegate_address, node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward == total_reward == delegate_info["Ret"]["CumulativeIncome"]
    end_balance = node.eth.getBalance(staking_address, switch_block)
    assert end_balance - start_balance == 0


@pytest.mark.P0
def test_DG_TR_016(delegate_node_client):
    """
    验证节点分红比例调整，验证分红池和节点收益
    :param delegate_node_client:
    :return:
    """
    update_reward = 2000
    node = delegate_node_client.node
    economic = delegate_node_client.economic

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(delegate_node_client.staking_address, switch_block)
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    result = delegate_node_client.staking.edit_candidate(delegate_node_client.staking_address,
                                                         delegate_node_client.staking_address, reward_per=update_reward)
    assert_code(result, 0)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["RewardPer"] == delegate_node_client.reward
    assert candidate_info["Ret"]["NextRewardPer"] == update_reward
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward_one, delegate_reward_one = calculate_reward(block_reward, staking_reward, block_num, delegate_node_client.reward)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward_one
    switch_block = calculate_switch_block(node, economic)
    end_balance_one = node.eth.getBalance(delegate_node_client.staking_address, switch_block)
    assert end_balance_one - start_balance == total_reward_one - delegate_reward_one
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["RewardPer"] == update_reward
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward_two, delegate_reward_two = calculate_reward(block_reward, staking_reward, block_num, update_reward)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward_two + delegate_reward_one
    end_balance_two = node.eth.getBalance(delegate_node_client.staking_address, switch_block)
    assert end_balance_two - end_balance_one == total_reward_two - delegate_reward_two


def test_DG_TR_017(delegate_node_client):
    """
    验证节点有委托时，退出重新质押
    :param delegate_node_client:
    :return:
    """
    reward = 2000
    node = delegate_node_client.node
    economic = delegate_node_client.economic

    economic.wait_settlement_blocknum(node)
    delegate_node_client.staking.withdrew_staking(delegate_node_client.staking_address)

    economic.wait_settlement_blocknum(node, number=2)
    staking_address, delegate_address = create_staking(delegate_node_client, reward)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["RewardPer"] == reward
    assert candidate_info["Ret"]["NextRewardPer"] == reward
    result = delegate_node_client.delegate.delegate(0, delegate_address)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == economic.calculate_delegate_reward(node, block_reward, staking_reward)


def test_DG_TR_018(delegate_node_client):
    """
    委托节点被双签处罚之后，验证当前节点产生的总委托奖励
    :param delegate_node_client:
    :return:
    """
    node = delegate_node_client.node
    economic = delegate_node_client.economic

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(delegate_node_client.staking_address, switch_block)
    block_reward, staking_reward = economic.get_current_year_reward(node)
    report_address, _ = economic.account.generate_account(node.web3, node.web3.toWei(1, "ether"))
    data = mock_duplicate_sign(1, node.nodekey, node.blsprikey, node.block_number)
    result = delegate_node_client.duplicatesign.reportDuplicateSign(1, data, report_address)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0
    assert node.eth.getBalance(node.web3.delegateRewardAddress) == 0
    block_num = economic.get_number_blocks_in_interval(node)
    end_balance = node.eth.getBalance(delegate_node_client.staking_address, switch_block)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, 0)
    assert end_balance - start_balance == total_reward


def test_DG_TR_018_2(delegate_node_client):
    """
    委托节点被双签处罚之后，验证当前节点产生的总委托奖励
    :param delegate_node_client:
    :return:
    """
    node = delegate_node_client.node
    economic = delegate_node_client.economic

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(delegate_node_client.staking_address, switch_block)
    block_reward_1, staking_reward_1 = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    block_reward_2, staking_reward_2 = economic.get_current_year_reward(node)
    report_address, _ = economic.account.generate_account(node.web3, node.web3.toWei(1, "ether"))
    block_num_1 = economic.get_number_blocks_in_interval(node)
    data = mock_duplicate_sign(1, node.nodekey, node.blsprikey, node.block_number)
    result = delegate_node_client.duplicatesign.reportDuplicateSign(1, data, report_address)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == economic.calculate_delegate_reward(node, block_reward_1, staking_reward_1)
    assert node.eth.getBalance(node.web3.delegateRewardAddress) == 0
    block_num_2 = economic.get_number_blocks_in_interval(node)
    end_balance = node.eth.getBalance(delegate_node_client.staking_address, switch_block)
    total_reward_1, delegate_reward_1 = calculate_reward(block_reward_1, staking_reward_1, block_num_1, 0)
    total_reward_2, delegate_reward_2 = calculate_reward(block_reward_2, staking_reward_2, block_num_2, 0)
    total = total_reward_1 + total_reward_2
    assert end_balance - start_balance == total


def test_DG_TR_019(client_new_node, reset_environment):
    """
    委托节点退出之后，验证当前节点产生的总委托奖励
    :param client_new_node:
    :return:
    """
    reward = 1000
    node = client_new_node.node
    economic = client_new_node.economic
    staking_address, delegate_address, ben_address = create_staking_dif_ben(client_new_node, reward)
    result = client_new_node.delegate.delegate(0, delegate_address)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    switch_block = calculate_switch_block(node, economic)
    start_balance = node.eth.getBalance(ben_address, switch_block)
    client_new_node.staking.withdrew_staking(staking_address)
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    end_balance = node.eth.getBalance(ben_address, switch_block + economic.settlement_size)
    block_num = economic.get_number_blocks_in_interval(node)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, reward)
    delegate_reward = economic.calculate_delegate_reward(node, block_reward, staking_reward)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward
    assert end_balance - start_balance == total_reward - delegate_reward


@pytest.mark.P1
def test_DG_TR_020(delegate_node_client):
    """
    赎回部分委托，验证当前节点产生的总委托奖励
    :param delegate_node_client:
    :return:
    """
    node = delegate_node_client.node
    economic = delegate_node_client.economic

    economic.wait_settlement_blocknum(node)
    block_reward, staking_reward = economic.get_current_year_reward(node)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    delegate_node_client.delegate.withdrew_delegate(candidate_info["Ret"]["StakingBlockNum"],
                                                    delegate_node_client.delegate_address, amount=delegate_node_client.economic.add_staking_limit)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0

    economic.wait_settlement_blocknum(node)
    block_num = economic.get_number_blocks_in_interval(node)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    total_reward, delegate_reward = calculate_reward(block_reward, staking_reward, block_num, delegate_node_client.reward)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == delegate_reward


@pytest.mark.P1
def test_DG_TR_021(delegate_node_client):
    """
    赎回全部委托，验证当前节点产生的总委托奖励
    :param delegate_node_client:
    :return:
    """
    node = delegate_node_client.node
    economic = delegate_node_client.economic

    economic.wait_settlement_blocknum(node)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    delegate_node_client.delegate.withdrew_delegate(candidate_info["Ret"]["StakingBlockNum"],
                                                    delegate_node_client.delegate_address,
                                                    amount=delegate_node_client.economic.add_staking_limit * 2)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0

    economic.wait_settlement_blocknum(node)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0


@pytest.mark.P1
def test_DG_TR_022(delegate_node_client):
    """
    节点被多次委托，验证当前节点产生的总委托奖励（同个结算期）
    :param delegate_node_client:
    :return:
    """
    node = delegate_node_client.node
    economic = delegate_node_client.economic
    result = delegate_node_client.delegate.delegate(0, delegate_node_client.delegate_address)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == economic.calculate_delegate_reward(node, block_reward,
                                                                                              staking_reward)


@pytest.mark.P1
def test_DG_TR_023(delegate_node_client):
    """
    节点被多次委托，验证当前节点产生的总委托奖励（跨结算期）
    :param delegate_node_client:
    :return:
    """
    node = delegate_node_client.node
    economic = delegate_node_client.economic

    economic.wait_settlement_blocknum(node)
    block_reward, staking_reward = economic.get_current_year_reward(node)
    result = delegate_node_client.delegate.delegate(0, delegate_node_client.delegate_address)
    assert_code(result, 0)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == 0

    economic.wait_settlement_blocknum(node)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    reward_total_one = economic.calculate_delegate_reward(node, block_reward, staking_reward)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == reward_total_one
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    candidate_info = delegate_node_client.ppos.getCandidateInfo(node.node_id)
    reward_total_two = economic.calculate_delegate_reward(node, block_reward, staking_reward)
    print(reward_total_two)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == reward_total_one + reward_total_two


def test_DG_TR_024(client_new_node, reset_environment):
    """
    节点被多个账号委托，验证当前节点产生的总委托奖励（同个结算期）
    :return:
    """
    reward = 1000
    node = client_new_node.node
    economic = client_new_node.economic
    create_staking(client_new_node, reward)
    delegate_address_1, _ = economic.account.generate_account(node.web3, economic.delegate_limit * 4)
    delegate_address_2, _ = economic.account.generate_account(node.web3, economic.delegate_limit * 4)
    result = client_new_node.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)
    result = client_new_node.delegate.delegate(0, delegate_address_2)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    reward_total = economic.calculate_delegate_reward(node, block_reward, staking_reward)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == reward_total


def test_DG_TR_025(client_new_node, reset_environment):
    """
    节点被多个账户委托，验证当前节点产生的总委托奖励（跨结算期）
    :return:
    """
    reward = 1000
    node = client_new_node.node
    economic = client_new_node.economic
    create_staking(client_new_node, reward)
    delegate_address_1, _ = economic.account.generate_account(node.web3, economic.delegate_limit * 4)
    delegate_address_2, _ = economic.account.generate_account(node.web3, economic.delegate_limit * 4)
    result = client_new_node.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)
    result = client_new_node.delegate.delegate(0, delegate_address_2)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    block_reward, staking_reward = economic.get_current_year_reward(node)
    result = client_new_node.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)
    result = client_new_node.delegate.delegate(0, delegate_address_2)
    assert_code(result, 0)

    economic.wait_settlement_blocknum(node)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    reward_total_one = economic.calculate_delegate_reward(node, block_reward, staking_reward)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == reward_total_one
    block_reward, staking_reward = economic.get_current_year_reward(node)

    economic.wait_settlement_blocknum(node)
    candidate_info = client_new_node.ppos.getCandidateInfo(node.node_id)
    reward_total_two = economic.calculate_delegate_reward(node, block_reward, staking_reward)
    assert candidate_info["Ret"]["DelegateRewardTotal"] == reward_total_two


def test_DG_TR_026(clients_noconsensus):
    """
    委托多个验证节点，验证当前节点产生的总委托奖励（同个结算期）
    :return:
    """
    client_1 = clients_noconsensus[0]
    client_2 = clients_noconsensus[1]
    reward_1 = 1000
    reward_2 = 2000
    node_1 = client_1.node
    node_2 = client_2.node
    economic_1 = client_1.economic
    economic_2 = client_2.economic
    create_staking(client_1, reward_1)
    create_staking(client_2, reward_2)
    delegate_address_1, _ = economic_1.account.generate_account(node_1.web3, economic_1.delegate_limit * 4)
    result = client_1.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)
    result = client_2.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)

    economic_1.wait_settlement_blocknum(node_1)
    block_reward, staking_reward = economic_1.get_current_year_reward(node_1)

    economic_1.wait_settlement_blocknum(node_1)
    candidate_info_1 = client_1.ppos.getCandidateInfo(node_1.node_id)
    reward_total_1 = economic_1.calculate_delegate_reward(node_1, block_reward, staking_reward)
    assert candidate_info_1["Ret"]["DelegateRewardTotal"] == reward_total_1
    reward_total_2 = economic_2.calculate_delegate_reward(node_2)
    candidate_info_2 = client_2.ppos.getCandidateInfo(node_2.node_id)
    assert candidate_info_2["Ret"]["DelegateRewardTotal"] == reward_total_2


def test_DG_TR_027(clients_noconsensus, reset_environment):
    """
    委托多个验证节点，验证当前节点产生的总委托奖励（跨结算期）
    :return:
    """
    client_1 = clients_noconsensus[0]
    client_2 = clients_noconsensus[1]
    reward_1 = 1000
    reward_2 = 2000
    node_1 = client_1.node
    node_2 = client_2.node
    economic_1 = client_1.economic
    economic_2 = client_2.economic
    create_staking(client_1, reward_1)
    create_staking(client_2, reward_2)
    delegate_address_1, _ = economic_1.account.generate_account(node_1.web3, economic_1.delegate_limit * 4)
    result = client_1.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)
    result = client_2.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)

    economic_1.wait_settlement_blocknum(node_1)
    block_reward, staking_reward = economic_1.get_current_year_reward(node_1)
    result = client_1.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)
    result = client_2.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)

    economic_1.wait_settlement_blocknum(node_1)
    candidate_info_1 = client_1.ppos.getCandidateInfo(node_1.node_id)
    reward_total_1_one = economic_1.calculate_delegate_reward(node_1, block_reward, staking_reward)
    assert candidate_info_1["Ret"]["DelegateRewardTotal"] == reward_total_1_one
    reward_total_2_one = economic_2.calculate_delegate_reward(node_2)
    candidate_info_2 = client_2.ppos.getCandidateInfo(node_2.node_id)
    assert candidate_info_2["Ret"]["DelegateRewardTotal"] == reward_total_2_one
    block_reward, staking_reward = economic_1.get_current_year_reward(node_1)

    economic_1.wait_settlement_blocknum(node_1)
    candidate_info_1 = client_1.ppos.getCandidateInfo(node_1.node_id)
    reward_total_1_two = economic_1.calculate_delegate_reward(node_1, block_reward, staking_reward)
    assert candidate_info_1["Ret"]["DelegateRewardTotal"] == reward_total_1_one + reward_total_1_two
    reward_total_2_two = economic_2.calculate_delegate_reward(node_2)
    candidate_info_2 = client_2.ppos.getCandidateInfo(node_2.node_id)
    assert candidate_info_2["Ret"]["DelegateRewardTotal"] == reward_total_2_one + reward_total_2_two


def test_DG_TR_028(clients_noconsensus, reset_environment):
    """
    多账户委托多个节点，验证当前节点产生的总委托奖励（同个结算期）
    :return:
    """
    client_1 = clients_noconsensus[0]
    client_2 = clients_noconsensus[1]
    reward_1 = 1000
    reward_2 = 2000
    node_1 = client_1.node
    node_2 = client_2.node
    economic_1 = client_1.economic
    economic_2 = client_2.economic
    create_staking(client_1, reward_1)
    create_staking(client_2, reward_2)
    delegate_address_1, _ = economic_1.account.generate_account(node_1.web3, economic_1.delegate_limit * 4)
    delegate_address_2, _ = economic_1.account.generate_account(node_1.web3, economic_1.delegate_limit * 4)
    result = client_1.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)
    result = client_2.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)
    result = client_1.delegate.delegate(0, delegate_address_2)
    assert_code(result, 0)
    result = client_2.delegate.delegate(0, delegate_address_2)
    assert_code(result, 0)

    economic_1.wait_settlement_blocknum(node_1)
    block_reward, staking_reward = economic_1.get_current_year_reward(node_1)

    economic_1.wait_settlement_blocknum(node_1)
    candidate_info_1 = client_1.ppos.getCandidateInfo(node_1.node_id)
    reward_total_1 = economic_1.calculate_delegate_reward(node_1, block_reward, staking_reward)
    assert candidate_info_1["Ret"]["DelegateRewardTotal"] == reward_total_1
    reward_total_2 = economic_2.calculate_delegate_reward(node_2)
    candidate_info_2 = client_2.ppos.getCandidateInfo(node_2.node_id)
    assert candidate_info_2["Ret"]["DelegateRewardTotal"] == reward_total_2


def test_DG_TR_029(clients_noconsensus, reset_environment):
    """
    多账户委托多个节点，验证当前节点产生的总委托奖励（跨结算期）
    :return:
    """
    client_1 = clients_noconsensus[0]
    client_2 = clients_noconsensus[1]
    reward_1 = 1000
    reward_2 = 2000
    node_1 = client_1.node
    node_2 = client_2.node
    economic_1 = client_1.economic
    economic_2 = client_2.economic
    create_staking(client_1, reward_1)
    create_staking(client_2, reward_2)
    delegate_address_1, _ = economic_1.account.generate_account(node_1.web3, economic_1.delegate_limit * 4)
    delegate_address_2, _ = economic_1.account.generate_account(node_1.web3, economic_1.delegate_limit * 4)
    result = client_1.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)
    result = client_2.delegate.delegate(0, delegate_address_1)
    assert_code(result, 0)
    result = client_1.delegate.delegate(0, delegate_address_2)
    assert_code(result, 0)
    result = client_2.delegate.delegate(0, delegate_address_2)
    assert_code(result, 0)

    economic_1.wait_settlement_blocknum(node_1)
    block_reward, staking_reward = economic_1.get_current_year_reward(node_1)

    economic_1.wait_settlement_blocknum(node_1)
    candidate_info_1 = client_1.ppos.getCandidateInfo(node_1.node_id)
    reward_total_1 = economic_1.calculate_delegate_reward(node_1, block_reward, staking_reward)
    assert candidate_info_1["Ret"]["DelegateRewardTotal"] == reward_total_1
    reward_total_2 = economic_2.calculate_delegate_reward(node_2)
    candidate_info_2 = client_2.ppos.getCandidateInfo(node_2.node_id)
    assert candidate_info_2["Ret"]["DelegateRewardTotal"] == reward_total_2

    economic_1.wait_settlement_blocknum(node_1)
    candidate_info_1 = client_1.ppos.getCandidateInfo(node_1.node_id)
    reward_total_1_2 = economic_1.calculate_delegate_reward(node_1, block_reward, staking_reward)
    assert candidate_info_1["Ret"]["DelegateRewardTotal"] == reward_total_1 + reward_total_1_2
    reward_total_2_2 = economic_2.calculate_delegate_reward(node_2)
    candidate_info_2 = client_2.ppos.getCandidateInfo(node_2.node_id)
    assert candidate_info_2["Ret"]["DelegateRewardTotal"] == reward_total_2 + reward_total_2_2


def test_DG_TR_030():
    """
    当前共识轮共识节点不在结算周期列表中，验证节点收益
    :return:
    """
    pass