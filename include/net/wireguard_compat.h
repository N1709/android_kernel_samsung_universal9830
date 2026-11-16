/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Compatibility shims for WireGuard on kernel 4.20
 * These functions/macros were added in later kernels
 */
#ifndef _NET_WIREGUARD_COMPAT_H
#define _NET_WIREGUARD_COMPAT_H

#include <linux/skbuff.h>
#include <linux/ip.h>
#include <linux/ipv6.h>
#include <net/dst_cache.h>

/* ip_tunnel_parse_protocol was added in 5.1+ */
static inline __be16 ip_tunnel_parse_protocol(const struct sk_buff *skb)
{
	if (skb_network_header(skb) >= skb->head &&
	    (skb_network_header(skb) + sizeof(struct iphdr)) <= skb_tail_pointer(skb) &&
	    ip_hdr(skb)->version == 4)
		return htons(ETH_P_IP);
	if (skb_network_header(skb) >= skb->head &&
	    (skb_network_header(skb) + sizeof(struct ipv6hdr)) <= skb_tail_pointer(skb) &&
	    ipv6_hdr(skb)->version == 6)
		return htons(ETH_P_IPV6);
	return 0;
}

/* skb_list_walk_safe was added in 5.1+ */
#define skb_list_walk_safe(first, skb, next_skb)				\
	for ((skb) = (first), (next_skb) = (skb) ? (skb)->next : NULL; (skb);	\
	     (skb) = (next_skb), (next_skb) = (skb) ? (skb)->next : NULL)

/* dst_cache_reset_now was added in 5.1+ */
static inline void dst_cache_reset_now(struct dst_cache *dst_cache)
{
	dst_cache_reset(dst_cache);
}

#endif /* _NET_WIREGUARD_COMPAT_H */
