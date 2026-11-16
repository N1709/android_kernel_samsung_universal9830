
/* NDO send wrapper for xfrm */
static inline void icmpv6_ndo_send(struct sk_buff *skb, u8 type, u8 code, __u32 info)
{
	icmpv6_send(skb, type, code, info);
}
