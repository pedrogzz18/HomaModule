#include "homa_impl.h"
#define KSELFTEST_NOT_MAIN 1
#include "kselftest_harness.h"
#include "ccutils.h"
#include "mock.h"
#include "utils.h"

FIXTURE(homa_plumbing) {
	__be32 client_ip;
	int client_port;
	__be32 server_ip;
	int server_port;
	__u64 rpcid;
	struct homa homa;
	struct homa_sock hsk;
	struct sockaddr_in server_addr;
	struct data_header data;
	int starting_skb_count;
};
FIXTURE_SETUP(homa_plumbing)
{
	self->client_ip = unit_get_in_addr("196.168.0.1");
	self->client_port = 40000;
	self->server_ip = unit_get_in_addr("1.2.3.4");
	self->server_port = 99;
	self->rpcid = 12345;
	self->server_addr.sin_family = AF_INET;
	self->server_addr.sin_addr.s_addr = self->server_ip;
	self->server_addr.sin_port = htons(self->server_port);
	homa = &self->homa;
	homa_init(&self->homa);
	mock_sock_init(&self->hsk, &self->homa, 0, 0);
	homa_sock_bind(&self->homa.port_map, &self->hsk, self->server_port);
	self->data = (struct data_header){.common = {
			.sport = htons(self->client_port),
	                .dport = htons(self->server_port), .id = self->rpcid,
			.type = DATA},
		        .message_length = htonl(10000), .offset = 0,
			.unscheduled = htonl(10000), .retransmit = 0};
	unit_log_clear();
}
FIXTURE_TEARDOWN(homa_plumbing)
{
	mock_sock_destroy(&self->hsk, &self->homa.port_map);
	homa_destroy(&self->homa);
	unit_teardown();
	homa = NULL;
}

TEST_F(homa_plumbing, homa_pkt_recv__packet_too_short)
{
	struct sk_buff *skb;
	skb = mock_skb_new(self->client_ip, &self->data.common, 1400, 1400);
	skb->len = 12;
	homa_pkt_recv(skb);
	EXPECT_EQ(0, unit_list_length(&self->hsk.server_rpcs));
}
TEST_F(homa_plumbing, homa_pkt_recv__unknown_socket)
{
	struct sk_buff *skb;
	self->data.common.dport = 100;
	skb = mock_skb_new(self->client_ip, &self->data.common, 1400, 1400);
	homa_pkt_recv(skb);
	EXPECT_EQ(0, unit_list_length(&self->hsk.server_rpcs));
}
TEST_F(homa_plumbing, homa_pkt_recv__use_backlog)
{
	struct sk_buff *skb;
	lock_sock((struct sock *) &self->hsk);
	skb = mock_skb_new(self->client_ip, &self->data.common, 1400, 1400);
	EXPECT_EQ(NULL, self->hsk.inet.sk.sk_backlog.head);
	homa_pkt_recv(skb);
	EXPECT_EQ(0, unit_list_length(&self->hsk.server_rpcs));
	EXPECT_EQ(skb, self->hsk.inet.sk.sk_backlog.head);
	kfree_skb(self->hsk.inet.sk.sk_backlog.head);
	release_sock((struct sock *) &self->hsk);
}